"""
Trajectory to the $20B FY2030 NGS ARR target.

The forecasting backtest (backtest.py) is about *accuracy* on the recent past. This module is about
*strategic planning*: project ORGANIC NGS ARR forward with the interpretable driver-based model
(so each scenario maps to assumptions a CFO can argue about), add the INORGANIC ramp from the
closed acquisitions, and measure the path to $20B by FY2030 under base / bull / bear scenarios.
It also solves the inverse question: how many platformizations are needed to close any gap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import db

from . import driver_based, utils

TARGET_2030 = 20e9
TARGET_MONTH = "2030-07"

# Scenario levers applied to the driver-based projection.
SCENARIOS = {
    "Base":  dict(exp_mult=1.00, churn_mult=1.00, new_mult=1.00, new_growth_add=0.000),
    "Bull":  dict(exp_mult=1.12, churn_mult=0.85, new_mult=1.10, new_growth_add=0.010),
    "Bear":  dict(exp_mult=0.88, churn_mult=1.20, new_mult=0.90, new_growth_add=-0.012),
}


def _months_to_target(history: pd.Series) -> int:
    last = history.index[-1]
    end = pd.Timestamp(TARGET_MONTH + "-01")
    return (end.year - last.year) * 12 + (end.month - last.month)


def _inorganic_forward(horizon: int, start_month: pd.Timestamp) -> pd.Series:
    """Project inorganic (CyberArk + Chronosphere) ARR forward from its last actual value.

    Growth decays toward the company average as the acquired books mature (no permanent triple-digit
    growth). Kept simple and transparent — the detailed M&A modelling lives in src/ma.py.
    """
    last = db.query("SELECT inorganic_ngs_arr FROM v_ngs_arr_summary ORDER BY month").iloc[-1, 0]
    idx = pd.date_range(start=start_month, periods=horizon, freq="MS")
    vals, cur = [], float(last)
    for h in range(horizon):
        g = 0.020 * (0.97 ** h) + 0.004     # decaying from ~2.4%/mo toward ~0.4%/mo
        cur *= (1 + g)
        vals.append(cur)
    return pd.Series(vals, index=idx)


def project(scenario: str = "Base") -> pd.DataFrame:
    """Full monthly path (history + forecast) of organic, inorganic and total NGS ARR."""
    organic_hist = utils.load_organic_ngs_arr()
    total_hist = utils.load_total_ngs_arr()
    horizon = _months_to_target(organic_hist)

    org_fc = driver_based.forecast(organic_hist, horizon, **SCENARIOS[scenario])
    inorg_fc = _inorganic_forward(horizon, org_fc.index[0])
    total_fc = org_fc + inorg_fc.reindex(org_fc.index).fillna(0)

    hist = pd.DataFrame({
        "month": total_hist.index, "organic": organic_hist.reindex(total_hist.index).to_numpy(),
        "total": total_hist.to_numpy(), "kind": "actual"})
    hist["inorganic"] = hist["total"] - hist["organic"]
    fc = pd.DataFrame({"month": org_fc.index, "organic": org_fc.to_numpy(),
                       "inorganic": inorg_fc.to_numpy(), "total": total_fc.to_numpy(),
                       "kind": "forecast"})
    out = pd.concat([hist, fc], ignore_index=True)
    out["scenario"] = scenario
    return out


def summary(scenario: str = "Base") -> dict:
    df = project(scenario)
    end = df[df["month"] == pd.Timestamp(TARGET_MONTH + "-01")]
    total_2030 = float(end["total"].iloc[0]) if len(end) else float(df["total"].iloc[-1])
    last_actual = df[df["kind"] == "actual"].iloc[-1]
    n_years = (pd.Timestamp(TARGET_MONTH + "-01").year - last_actual["month"].year)
    cagr = (total_2030 / last_actual["total"]) ** (1 / max(n_years, 1)) - 1
    return {
        "scenario": scenario,
        "ngs_arr_2030": total_2030,
        "target": TARGET_2030,
        "gap_to_target": TARGET_2030 - total_2030,
        "pct_of_target": total_2030 / TARGET_2030,
        "implied_cagr_to_2030": cagr,
        "hits_target": total_2030 >= TARGET_2030,
    }


def scenario_table() -> pd.DataFrame:
    return pd.DataFrame([summary(s) for s in SCENARIOS])


def required_platformizations(scenario: str = "Base", target: float = TARGET_2030) -> dict:
    """Solve: how many *additional* platformizations close the gap to $20B by FY2030?

    Mechanism: a platformized customer retains/expands far better (the NRR gap). We translate the
    gap-to-target into incremental ARR per platformization using the observed platformized-vs-not
    ARR-per-customer uplift compounded over the years remaining, then divide.
    """
    s = summary(scenario)
    gap = max(s["gap_to_target"], 0.0)
    # observed average ARR per customer, platformized vs not, at the latest actual quarter
    uplift = db.query("""
        WITH last AS (SELECT MAX(month) AS m FROM customer_arr_monthly)
        SELECT c.platformized_flag, AVG(cam.arr) AS avg_arr
        FROM customer_arr_monthly cam
        JOIN dim_customer c ON c.customer_id = cam.customer_id
        WHERE cam.month = (SELECT m FROM last) AND cam.arr > 0
        GROUP BY c.platformized_flag
    """)
    avg_plat = float(uplift.loc[uplift["platformized_flag"], "avg_arr"].iloc[0])
    avg_non = float(uplift.loc[~uplift["platformized_flag"], "avg_arr"].iloc[0])
    incremental_arr_per_platformization = max(avg_plat - avg_non, 1.0)

    n_needed = int(np.ceil(gap / incremental_arr_per_platformization)) if gap > 0 else 0
    base_plat = int(db.query(
        "SELECT COUNT(*) FROM dim_customer WHERE platformized_flag").iloc[0, 0])
    return {
        "scenario": scenario,
        "gap_to_target": gap,
        "avg_arr_platformized": avg_plat,
        "avg_arr_non_platformized": avg_non,
        "incremental_arr_per_platformization": incremental_arr_per_platformization,
        "additional_platformizations_needed": n_needed,
        "current_platformized": base_plat,
        "implied_total_platformized": base_plat + n_needed,
        "company_target_platformizations": 4000,
    }


if __name__ == "__main__":
    print("=== Scenario table (NGS ARR at FY2030) ===")
    st = scenario_table()
    for r in st.itertuples():
        print(f"  {r.scenario:5s}: ${r.ngs_arr_2030/1e9:5.1f}B  ({r.pct_of_target*100:4.0f}% of $20B)"
              f"  CAGR {r.implied_cagr_to_2030*100:4.1f}%  hits={r.hits_target}")
    print("\n=== Required platformizations to hit $20B (Base) ===")
    for k, v in required_platformizations("Base").items():
        print(f"  {k:42s}: {v}")
