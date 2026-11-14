"""Fase 2 - Calcula os indicadores e a pontuacao e grava as tabelas em data/.

Uso:
    python scripts/indicators.py

Saidas:
    data/indicadores_clima.csv        um registo por ano (o que os dados NASA mostram)
    data/indicadores_culturas.csv     um registo por ano e cultura
    data/indicadores_estrategias.csv  um registo por ano e estrategia
    data/pontuacao_cenarios.csv       ordenacao por cenario, com pesos iguais
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fieldshift import config as cfg, indicators as ind, scoring as sc  # noqa: E402

DATA = ROOT / "data"


def main():
    d = pd.read_csv(DATA / "power_braganca_daily.csv", parse_dates=["date"], index_col="date")
    clim = ind.climate_indicators(d)
    crops = ind.crop_year_table(d)
    strat = ind.strategy_year_table(crops)
    clim.to_csv(DATA / "indicadores_clima.csv")
    crops.round(1).to_csv(DATA / "indicadores_culturas.csv", index=False)
    strat.round(2).to_csv(DATA / "indicadores_estrategias.csv", index=False)

    sub = sc.subscores(strat, sc.reference_scales(strat))
    scenarios = {
        "todos os anos": None,
        "anos secos": clim.index[clim["tipo_ano"] == "seco"],
        "anos de chuva intensa": clim.index[clim["tipo_ano"] == "chuva intensa"],
    }
    frames = []
    for name, years in scenarios.items():
        res = sc.summarise(sub, cfg.DEFAULT_WEIGHTS, years).reset_index()
        res.insert(0, "cenario", name)
        frames.append(res)
    out = pd.concat(frames, ignore_index=True).round(3)
    out.to_csv(DATA / "pontuacao_cenarios.csv", index=False)

    print(clim[["precip_mm", "t_media", "dias_geada", "dias_chuva_intensa", "tipo_ano"]].to_string())
    print()
    print(strat.drop(columns="ano").groupby("estrategia").mean().round(1).T.to_string())
    print()
    print(out[["cenario", "posicao", "estrategia", "pontuacao", "p10", "p90", "pct_anos_1o"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
