"""Indicadores de clima do local e indicadores por cultura e por estratégia.

Separação importante:
  (a) climate_indicators: o que os dados NASA mostram sobre o local;
  (b) crop_year_table / strategy_year_table: como cada rotação fica exposta a
      essas condições, segundo um calendário de culturas que é uma hipótese.
"""
import numpy as np
import pandas as pd

from . import config as cfg


def window_mask(idx: pd.DatetimeIndex, windows) -> np.ndarray:
    """True nos dias dentro de alguma janela ((mês, dia), (mês, dia))."""
    md = idx.month * 100 + idx.day
    mask = np.zeros(len(idx), dtype=bool)
    for (m0, d0), (m1, d1) in windows:
        mask |= (md >= m0 * 100 + d0) & (md <= m1 * 100 + d1)
    return mask


def reference_et(d: pd.DataFrame) -> np.ndarray:
    """ET de referência (mm/dia), fórmula de Hargreaves com radiação medida.

    ET0 = 0,0135 x (T + 17,8) x Rs, com Rs em mm/dia (MJ/m2/dia a dividir por 2,45).
    """
    rs_mm = d["ALLSKY_SFC_SW_DWN"].to_numpy(dtype=float) / 2.45
    t = d["T2M"].to_numpy(dtype=float)
    return np.clip(0.0135 * (t + 17.8) * rs_mm, 0, None)


def climate_indicators(d: pd.DataFrame) -> pd.DataFrame:
    """Um registo por ano: totais, extremos, anomalias e tipo de ano."""
    et0 = pd.Series(reference_et(d), index=d.index)
    y = d.groupby(d.index.year)
    out = pd.DataFrame({
        "precip_mm": y["PRECTOTCORR"].sum(),
        "et0_mm": et0.groupby(et0.index.year).sum(),
        "t_media": y["T2M"].mean(),
        "dias_geada": y["T2M_MIN"].apply(lambda s: int((s < 0).sum())),
        "dias_chuva_intensa": y["PRECTOTCORR"].apply(lambda s: int((s >= cfg.HEAVY_RAIN_MM).sum())),
        "dias_calor_30": y["T2M_MAX"].apply(lambda s: int((s >= 30).sum())),
    })
    if "GWETROOT" in d:
        out["dias_solo_seco"] = y["GWETROOT"].apply(lambda s: int((s < cfg.DRY_ROOT_WETNESS).sum()))
    out.index.name = "ano"
    for col in ["precip_mm", "t_media", "dias_geada", "dias_chuva_intensa"]:
        out[f"anom_{col}"] = out[col] - out[col].mean()
    p, h = out["precip_mm"], out["dias_chuva_intensa"]
    out["tipo_ano"] = np.where(p <= p.quantile(0.2), "seco",
                               np.where(h >= h.quantile(0.8), "chuva intensa", "normal"))
    return out.round(2)


def _water_deficit(d: pd.DataFrame, crop: dict, et0: np.ndarray):
    """Balanço de água diário num 'balde' de solo, contínuo ao longo da série.

    Devolve, por dia, a procura da cultura e a parte que o solo não conseguiu dar.
    """
    season = window_mask(d.index, crop["season"])
    cover = window_mask(d.index, crop["cover"])
    kc = np.where(season, crop["kc"], np.where(cover, 0.5, cfg.KC_BARE))
    demand = kc * et0
    rain = d["PRECTOTCORR"].to_numpy(dtype=float)
    deficit = np.zeros(len(d))
    s = cfg.SOIL_AWC_MM
    for i in range(len(d)):
        s = min(cfg.SOIL_AWC_MM, s + rain[i]) - demand[i]
        if s < 0:
            deficit[i] = -s
            s = 0.0
    return np.where(season, demand, 0.0), np.where(season, deficit, 0.0)


def crop_year_table(d: pd.DataFrame, crops: dict | None = None) -> pd.DataFrame:
    """Um registo por ano e cultura, com os indicadores de exposição."""
    crops = crops or cfg.CROPS
    et0 = reference_et(d)
    years = d.index.year
    rain = d["PRECTOTCORR"].to_numpy(dtype=float)
    tmin = d["T2M_MIN"].to_numpy(dtype=float)
    heavy = rain >= cfg.HEAVY_RAIN_MM
    frames = []
    for name, c in crops.items():
        cover = window_mask(d.index, c["cover"])
        demand, deficit = _water_deficit(d, c, et0)
        frost = np.zeros(len(d), dtype=bool)
        if c["frost_t"] is not None:
            frost = window_mask(d.index, c["frost"]) & (tmin < c["frost_t"])
        df = pd.DataFrame({
            "ano": years,
            "dias_solo_nu": ~cover,
            "chuva_intensa_solo_nu_mm": np.where(heavy & ~cover, rain, 0.0),
            "procura_agua_mm": demand,
            "defice_hidrico_mm": deficit,
            "dias_geada_sensivel": frost,
        }).groupby("ano").sum().reset_index()
        df.insert(1, "cultura", name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def strategy_year_table(crop_table: pd.DataFrame, strategies: dict | None = None,
                        crops: dict | None = None, irrigated_potato: bool = False,
                        margin_case: int = 1) -> pd.DataFrame:
    """Um registo por ano e estratégia.

    Cada fase da rotação ocupa um terço da exploração no mesmo ano (três
    parcelas), por isso os valores são a média das três culturas.
    margin_case: 0 = margem baixa, 1 = central, 2 = alta.
    """
    strategies = strategies or cfg.STRATEGIES
    crops = crops or cfg.CROPS
    ct = crop_table.set_index(["cultura", "ano"])
    num = ["dias_solo_nu", "chuva_intensa_solo_nu_mm", "procura_agua_mm",
           "defice_hidrico_mm", "dias_geada_sensivel"]
    rows = []
    for key, s in strategies.items():
        parts = []
        for crop in s["culturas"]:
            part = ct.loc[crop, num].copy()
            if irrigated_potato and crop == "batata":
                part["rega_mm"] = part["defice_hidrico_mm"]
                part["defice_hidrico_mm"] = 0.0
            else:
                part["rega_mm"] = 0.0
            parts.append(part)
        mean = sum(parts) / len(parts)
        mean["estrategia"] = key
        mean["materia_organica"] = np.mean([crops[c]["mo"] for c in s["culturas"]])
        mean["azoto_fixado_kg"] = np.mean([crops[c]["n_fix"] for c in s["culturas"]])
        mean["margem_eur_ha"] = np.mean([crops[c]["margem"][margin_case] for c in s["culturas"]])
        rows.append(mean.reset_index())
    out = pd.concat(rows, ignore_index=True)
    return out[["ano", "estrategia"] + num + ["rega_mm", "materia_organica",
                                               "azoto_fixado_kg", "margem_eur_ha"]]
