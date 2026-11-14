"""Pontuação ponderada das estratégias, com incerteza explícita.

Cada critério é convertido numa nota de 0 a 1 (1 = melhor) contra uma escala
de referência fixa, calculada sobre todo o histórico. Assim a nota de uma
estratégia não muda só porque se acrescentou ou retirou outra à comparação.
A pontuação final é a soma das notas, ponderada pelas prioridades do agricultor.
"""
import numpy as np
import pandas as pd

from . import config as cfg

CRITERIA = list(cfg.CRITERIA)  # ordem fixa: agua, receita, erosao, materia_organica, geada
LOWER_IS_BETTER = {"agua": "defice_hidrico_mm", "erosao": "chuva_intensa_solo_nu_mm",
                   "geada": "dias_geada_sensivel"}


def normalise_weights(weights) -> np.ndarray:
    """Aceita dict ou vetor; devolve pesos não negativos que somam 1."""
    if isinstance(weights, dict):
        weights = [weights.get(c, 0) for c in CRITERIA]
    w = np.clip(np.asarray(weights, dtype=float), 0, None)
    return w / w.sum() if w.sum() > 0 else np.full(len(CRITERIA), 1 / len(CRITERIA))


def reference_scales(strategy_years: pd.DataFrame) -> dict:
    """Escalas fixas: o pior valor observado em qualquer ano e estratégia."""
    refs = {c: float(strategy_years[col].max()) for c, col in LOWER_IS_BETTER.items()}
    refs["receita"] = float(strategy_years["margem_eur_ha"].max())
    return refs


def subscores(strategy_years: pd.DataFrame, refs: dict) -> pd.DataFrame:
    """Notas de 0 a 1 por critério, por ano e estratégia."""
    out = strategy_years[["ano", "estrategia"]].copy()
    for c, col in LOWER_IS_BETTER.items():
        ref = refs[c]
        out[c] = 1.0 if ref <= 0 else (1 - strategy_years[col] / ref).clip(0, 1)
    ref = refs["receita"]
    out["receita"] = 0.0 if ref <= 0 else (strategy_years["margem_eur_ha"] / ref).clip(0, 1)
    out["materia_organica"] = strategy_years["materia_organica"].clip(0, 1)
    return out[["ano", "estrategia"] + CRITERIA]


def score_years(sub: pd.DataFrame, weights) -> pd.DataFrame:
    """Pontuação (0 a 100) por ano e estratégia."""
    w = normalise_weights(weights)
    out = sub[["ano", "estrategia"]].copy()
    out["pontuacao"] = 100 * sub[CRITERIA].to_numpy() @ w
    return out


def summarise(sub: pd.DataFrame, weights, years=None) -> pd.DataFrame:
    """Ordenação das estratégias nos anos escolhidos, com a variação entre anos.

    p10 e p90: intervalo em que a pontuação fica em 8 de cada 10 anos.
    pct_anos_1o: percentagem de anos em que a estratégia fica em primeiro.
    """
    if years is not None:
        sub = sub[sub["ano"].isin(list(years))]
    sy = score_years(sub, weights)
    wide = sy.pivot(index="ano", columns="estrategia", values="pontuacao")
    best = wide.eq(wide.max(axis=1), axis=0)
    res = pd.DataFrame({
        "pontuacao": wide.mean(),
        "p10": wide.quantile(0.1),
        "p90": wide.quantile(0.9),
        "pct_anos_1o": 100 * best.mean(),
    })
    means = sub.groupby("estrategia")[CRITERIA].mean()
    res = res.join(means).sort_values("pontuacao", ascending=False)
    res.insert(0, "posicao", range(1, len(res) + 1))
    res["n_anos"] = wide.shape[0]
    return res


def criteria_matrix(sub: pd.DataFrame, years=None) -> pd.DataFrame:
    """Nota média por estratégia e critério (linhas = estratégias)."""
    if years is not None:
        sub = sub[sub["ano"].isin(list(years))]
    return sub.groupby("estrategia")[CRITERIA].mean()
