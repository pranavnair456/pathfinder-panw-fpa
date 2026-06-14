"""Metric-correctness tests."""
from src import metrics


def test_kpi_snapshot_in_plausible_ranges():
    s = metrics.kpi_snapshot()
    assert 7e9 < s["ngs_arr"] < 10e9              # ~$8-9B calibrated
    assert 0.40 < s["ngs_arr_yoy"] < 0.75         # high-50s% incl. inorganic
    assert 1.05 < s["nrr"] < 1.40                 # ~120%
    assert 0.30 < s["fcf_margin"] < 0.45
    assert s["platformized"] >= 2000
    assert abs(s["ngs_arr_organic"] + s["ngs_arr_inorganic"] - s["ngs_arr"]) < 1.0


def test_nrr_gap_platformized_higher():
    df = metrics.nrr_by_platformization()
    latest = df["month"].max()
    d = df[df["month"] == latest].set_index("platformized_flag")["nrr"]
    assert d[True] > d[False], "platformized NRR should exceed non-platformized"
    assert d[True] > 1.20


def test_rule_of_40_positive_and_reasonable():
    r = metrics.rule_of_40()
    assert (r["rule_of_40"].tail(4) > 40).all()


def test_arr_rollforward_total_matches_summary():
    rf = metrics.arr_rollforward_total()
    summ = metrics.ngs_arr_summary()
    last_rf = rf.iloc[-1]["ending_arr"]
    last_sum = summ.iloc[-1]["total_ngs_arr"]
    assert abs(last_rf - last_sum) / last_sum < 0.001
