"""Testes do núcleo: indicadores, pontuação, PSO e arranque da aplicação.

Correr a partir da pasta do projeto:  python -m pytest -q
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fieldshift import config as cfg, indicators as ind, pso, scoring as sc

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def daily():
    return pd.read_csv(ROOT / "data" / "power_braganca_daily.csv", parse_dates=["date"], index_col="date")


@pytest.fixture(scope="module")
def tables(daily):
    clim = ind.climate_indicators(daily)
    crops = ind.crop_year_table(daily)
    strat = ind.strategy_year_table(crops)
    sub = sc.subscores(strat, sc.reference_scales(strat))
    return clim, crops, strat, sub


def test_daily_series_is_complete(daily):
    assert daily.index.min() == pd.Timestamp("2000-01-01")
    assert daily.index.max() == pd.Timestamp("2025-12-31")
    assert len(daily) == 9497 and not daily.isna().any().any()


def test_window_mask_handles_split_windows():
    idx = pd.date_range("2021-01-01", "2021-12-31")
    mask = ind.window_mask(idx, [((1, 1), (1, 31)), ((12, 1), (12, 31))])
    assert mask.sum() == 62


def test_climate_is_plausible_for_braganca(tables):
    clim = tables[0]
    assert 500 < clim["precip_mm"].mean() < 1000
    assert 9 < clim["t_media"].mean() < 14
    assert set(clim["tipo_ano"]) == {"seco", "normal", "chuva intensa"}


def test_fallow_is_always_bare_and_needs_no_water(tables):
    fallow = tables[1][tables[1]["cultura"] == "pousio"]
    assert (fallow["dias_solo_nu"] >= 365).all()
    assert (fallow["defice_hidrico_mm"] == 0).all()


def test_replacing_fallow_reduces_bare_soil(tables):
    bare = tables[2].groupby("estrategia")["dias_solo_nu"].mean()
    assert bare["A"] > bare[["B", "C", "D"]].max()


def test_irrigation_removes_potato_deficit(tables):
    wet = ind.strategy_year_table(tables[1], irrigated_potato=True)
    dry = tables[2]
    assert wet["defice_hidrico_mm"].sum() < dry["defice_hidrico_mm"].sum()
    assert wet["rega_mm"].sum() > 0


def test_subscores_are_between_0_and_1(tables):
    vals = tables[3][sc.CRITERIA].to_numpy()
    assert vals.min() >= 0 and vals.max() <= 1


def test_weights_are_normalised():
    assert sc.normalise_weights({"agua": 10}).tolist() == [1, 0, 0, 0, 0]
    assert np.isclose(sc.normalise_weights([0, 0, 0, 0, 0]).sum(), 1)


def test_single_criterion_ranking_follows_that_criterion(tables):
    res = sc.summarise(tables[3], {"materia_organica": 10})
    assert res.index[0] == "C"   # a forragem tem o maior índice de matéria orgânica
    assert res.index[-1] == "A"  # o pousio tem o menor


def test_summary_scores_stay_in_range(tables):
    res = sc.summarise(tables[3], cfg.DEFAULT_WEIGHTS)
    assert res["pontuacao"].between(0, 100).all()
    assert (res["p10"] <= res["pontuacao"]).all() and (res["pontuacao"] <= res["p90"]).all()


def test_pso_finds_minimum_of_simple_function():
    x, val, hist = pso.pso_minimise(lambda x: ((x - 0.3) ** 2).sum(axis=1), dim=3)
    assert val < 1e-6 and np.allclose(x, 0.3, atol=1e-2)
    assert hist[-1] <= hist[0]


def test_flip_distance_really_flips_the_winner(tables):
    m = sc.criteria_matrix(tables[3]).to_numpy()
    w = sc.normalise_weights(cfg.DEFAULT_WEIGHTS)
    r = pso.flip_distance(m, w)
    assert r is not None and r["vencedor_depois"] != r["vencedor_antes"]
    assert np.isclose(r["pesos"].sum(), 1) and 0 < r["distancia"] < 1


def test_flip_distance_is_none_when_one_strategy_dominates():
    m = np.array([[1.0, 1.0, 1.0], [0.5, 0.5, 0.5]])
    assert pso.flip_distance(m, np.array([1 / 3, 1 / 3, 1 / 3])) is None


def test_calibration_reproduces_a_feasible_ranking(tables):
    m = sc.criteria_matrix(tables[3])
    order = list(sc.summarise(tables[3], {"erosao": 6, "receita": 4}).index)
    r = pso.calibrate_to_ranking(m.to_numpy(), [list(m.index).index(k) for k in order])
    assert r["pares_errados"] == 0


def test_app_runs_and_reacts_to_inputs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("Anos secos").run()
    at.sidebar.checkbox[0].set_value(True).run()   # rega
    at.sidebar.checkbox[1].set_value(False).run()  # sem destino para forragem
    at.sidebar.slider[0].set_value(10).run()
    at.multiselect[0].set_value(["B", "D", "C", "A"]).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("Um ano").run()
    assert not at.exception


def test_ndvi_confirms_bare_summer_in_cereal_fields():
    """NDVI do Sentinel-2: as três parcelas de cereal ficam sem vegetação verde no verão."""
    files = sorted((ROOT / "data").glob("ndvi_braganca_field*_monthly.csv"))
    assert len(files) == 3
    for f in files:
        d = pd.read_csv(f)
        assert list(d["month"]) == list(range(1, 13))
        assert d["ndvi_median"].between(-1, 1).all()
        assert (d.loc[d["month"].isin([7, 8, 9]), "ndvi_median"] < 0.25).all()


def test_high_margins_do_not_tie_all_strategies(tables):
    """Com escala de receita própria, as margens altas continuam a distinguir as estratégias."""
    _, crops, _, _ = tables
    sy = ind.strategy_year_table(crops, margin_case=2)
    res = sc.summarise(sc.subscores(sy, sc.reference_scales(sy)), {"receita": 1})
    assert res["pontuacao"].nunique() == len(res)
    assert res.index[0] == "C"
