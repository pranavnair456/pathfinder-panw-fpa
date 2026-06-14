"""Forecasting, trajectory, platformization and M&A model tests."""
from src import ma, platformization
from src.forecast import baseline, driver_based, trajectory, utils


def test_models_return_horizon_length():
    s = utils.load_organic_ngs_arr()
    for fn in (baseline.seasonal_naive, baseline.naive_drift, driver_based.forecast):
        fc = fn(s, 6)
        assert len(fc) == 6
        assert (fc > 0).all()


def test_backtest_cache_chosen_beats_baseline():
    from src.forecast import backtest
    bt = backtest.load_cached()
    assert bt is not None, "run python -m src.forecast.backtest to cache results"
    summ = {r["model"]: r for r in bt["summary"]}
    base = summ["Seasonal-Naive"]["flow_WAPE"]
    best = summ[bt["best_model"]]["flow_WAPE"]
    assert best <= base, "best model should not be worse than the baseline"


def test_threat_ablation_lift_recorded():
    from src import threat_signals
    c = threat_signals.load_cached()
    assert c is not None
    abl = c["ablation"]
    # threat helps near-term and beats the naive baseline in the 1-step ablation
    assert abl["threat_helps"] is True
    assert abl["beats_seasonal_naive"] is True


def test_trajectory_scenarios_ordered():
    st = trajectory.scenario_table().set_index("scenario")
    assert st.loc["Bear", "ngs_arr_2030"] < st.loc["Base", "ngs_arr_2030"] < st.loc["Bull", "ngs_arr_2030"]


def test_platformization_roi_positive_npv():
    a = platformization.default_assumptions_from_data()
    res = platformization.incentive_roi(a)
    assert res["npv"] > 0
    assert res["irr"] is None or res["irr"] > 0
    # NPV most sensitive to the NRR gap
    tor = platformization.tornado(a)
    assert tor.iloc[0]["driver"] in ("nrr_platformized", "nrr_counterfactual")


def test_ma_npv_and_accretion_shape():
    a = ma.DealAssumptions()
    ad = ma.accretion_dilution(a)
    npv = ma.deal_npv(a)
    assert "eps_accretion_dilution_pct" in ad
    assert ad["proforma_eps"] > 0
    assert npv["enterprise_value_created"] > 0
    assert npv["implied_arr_multiple"] > 1


def test_decomposition_inorganic_share_reasonable():
    d = ma.latest_split()
    assert 0.10 < d["inorganic_share"] < 0.35
    assert d["organic"] + d["inorganic"] == d["total"] or abs(
        d["organic"] + d["inorganic"] - d["total"]) < 1.0
