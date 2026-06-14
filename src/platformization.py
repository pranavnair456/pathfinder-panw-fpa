"""
Option B — Platformization economics & incentive ROI.

The thesis in one line: a *platformized* customer (one that has consolidated multiple PANW
products onto the platform) retains and expands far better than a single-product customer. We saw
it in the data — ~135% NRR platformized vs ~114% not. This module (1) quantifies that gap as
cohort economics, and (2) models the ROI of *spending* to convert customers (PANW's platformization
incentives) as an NPV / IRR / payback decision, with a tornado sensitivity.

Finance reasoning behind the ROI model:
    Converting a customer is an INVESTMENT: pay an incentive now (a credit/discount), earn a stream
    of *incremental* gross profit later because the customer now grows at the platformized NRR
    instead of the lower standalone NRR. Incremental ARR in year t = starting ARR ×
    (NRR_plat^t − NRR_non^t); gross-profit cash flow = that × gross margin. Discount it -> NPV.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src import db, metrics


# ---------------------------------------------------------------------------
# Cohort economics (observed in the data)
# ---------------------------------------------------------------------------
def cohort_economics(month: str | None = None) -> pd.DataFrame:
    """Platformized vs non-platformized: customer count, avg ARR, total ARR, NRR, GRR."""
    if month is None:
        month = db.query("SELECT MAX(month) m FROM customer_arr_monthly").iloc[0, 0]
    base = db.query("""
        SELECT c.platformized_flag,
               COUNT(*) FILTER (WHERE cam.arr > 0)              AS customers,
               AVG(cam.arr) FILTER (WHERE cam.arr > 0)          AS avg_arr,
               SUM(cam.arr)                                     AS total_arr
        FROM customer_arr_monthly cam
        JOIN dim_customer c ON c.customer_id = cam.customer_id
        WHERE cam.month = ?
        GROUP BY c.platformized_flag
    """, [month])
    nrr = metrics.nrr_by_platformization()
    nrr = nrr[nrr["month"] == month][["platformized_flag", "nrr", "grr"]]
    out = base.merge(nrr, on="platformized_flag", how="left")
    out["platformized_flag"] = out["platformized_flag"].map({True: "Platformized",
                                                             False: "Non-platformized"})
    return out


def observed_nrr_gap(month: str | None = None) -> tuple[float, float]:
    df = metrics.nrr_by_platformization()
    if month is None:
        month = df["month"].max()
    d = df[df["month"] == month]
    plat = float(d[d["platformized_flag"]]["nrr"].iloc[0])
    non = float(d[~d["platformized_flag"]]["nrr"].iloc[0])
    return plat, non


# ---------------------------------------------------------------------------
# Finance helpers
# ---------------------------------------------------------------------------
def npv(rate: float, cashflows: list[float]) -> float:
    return float(sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows)))


def irr(cashflows: list[float], lo: float = -0.95, hi: float = 5.0) -> float | None:
    """IRR via bisection on NPV sign change. Returns None if no root in range."""
    f_lo, f_hi = npv(lo, cashflows), npv(hi, cashflows)
    if np.sign(f_lo) == np.sign(f_hi):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < 1e-6:
            return mid
        if np.sign(f_mid) == np.sign(f_lo):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2


def payback_period(cashflows: list[float]) -> float | None:
    """Years to recover the initial outlay (with fractional interpolation)."""
    cum = np.cumsum(cashflows)
    for t in range(1, len(cum)):
        if cum[t] >= 0:
            prev = cum[t - 1]
            return (t - 1) + (-prev) / (cum[t] - prev) if cum[t] != prev else float(t)
    return None


# ---------------------------------------------------------------------------
# Incentive ROI model
# ---------------------------------------------------------------------------
@dataclass
class IncentiveAssumptions:
    target_customers: int = 1000          # eligible accounts in the campaign
    conversion_rate: float = 0.35         # fraction that actually platformize
    incentive_cost_per_conversion: float = 120_000   # upfront credit/discount per converted acct
    starting_arr_per_customer: float = 460_000        # avg ARR of a convertible (non-plat) account
    nrr_platformized: float = 1.30        # post-conversion NRR
    nrr_counterfactual: float = 1.10      # NRR had they NOT platformized
    gross_margin: float = 0.765
    horizon_years: int = 5
    discount_rate: float = 0.10
    ongoing_cost_pct: float = 0.0         # optional ongoing incentive as % of incremental ARR


def incentive_roi(a: IncentiveAssumptions) -> dict:
    """Return ARR uplift, NPV, IRR, payback and the yearly cash-flow schedule."""
    n = a.target_customers * a.conversion_rate
    upfront = -a.incentive_cost_per_conversion * n
    cashflows = [upfront]
    schedule = [{"year": 0, "incremental_arr": 0.0, "gross_profit": 0.0,
                 "incentive_cost": upfront, "net_cash": upfront}]
    for t in range(1, a.horizon_years + 1):
        incr_arr = a.starting_arr_per_customer * n * (a.nrr_platformized ** t - a.nrr_counterfactual ** t)
        gp = incr_arr * a.gross_margin
        ongoing = -a.ongoing_cost_pct * incr_arr
        net = gp + ongoing
        cashflows.append(net)
        schedule.append({"year": t, "incremental_arr": incr_arr, "gross_profit": gp,
                         "incentive_cost": ongoing, "net_cash": net})
    arr_uplift_end = a.starting_arr_per_customer * n * (
        a.nrr_platformized ** a.horizon_years - a.nrr_counterfactual ** a.horizon_years)
    return {
        "converted_customers": n,
        "total_incentive_spend": -upfront,
        "arr_uplift_year_end": arr_uplift_end,
        "npv": npv(a.discount_rate, cashflows),
        "irr": irr(cashflows),
        "payback_years": payback_period(cashflows),
        "roi_multiple": (npv(a.discount_rate, cashflows) + (-upfront)) / max(-upfront, 1),
        "cashflows": cashflows,
        "schedule": pd.DataFrame(schedule),
    }


def tornado(a: IncentiveAssumptions, pct: float = 0.25) -> pd.DataFrame:
    """One-at-a-time sensitivity of NPV to ±pct moves in each key driver."""
    base = incentive_roi(a)["npv"]
    drivers = ["conversion_rate", "incentive_cost_per_conversion", "nrr_platformized",
               "nrr_counterfactual", "starting_arr_per_customer", "discount_rate", "gross_margin"]
    rows = []
    for d in drivers:
        v = getattr(a, d)
        lo_a, hi_a = IncentiveAssumptions(**a.__dict__), IncentiveAssumptions(**a.__dict__)
        setattr(lo_a, d, v * (1 - pct))
        setattr(hi_a, d, v * (1 + pct))
        npv_lo, npv_hi = incentive_roi(lo_a)["npv"], incentive_roi(hi_a)["npv"]
        rows.append({"driver": d, "npv_low": npv_lo, "npv_high": npv_hi,
                     "swing": abs(npv_hi - npv_lo)})
    return pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)


def default_assumptions_from_data() -> IncentiveAssumptions:
    """Seed the calculator with values observed in the warehouse."""
    eco = cohort_economics()
    non = eco[eco["platformized_flag"] == "Non-platformized"]
    plat, noncf = observed_nrr_gap()
    start_arr = float(non["avg_arr"].iloc[0]) if len(non) else 460_000
    return IncentiveAssumptions(
        starting_arr_per_customer=round(start_arr, -3),
        nrr_platformized=round(plat, 2),
        nrr_counterfactual=round(noncf, 2),
        incentive_cost_per_conversion=round(0.25 * start_arr, -3),  # ~25% of first-year ARR
    )


if __name__ == "__main__":
    print("=== Cohort economics ===")
    print(cohort_economics().to_string(index=False))
    a = default_assumptions_from_data()
    print("\n=== Default assumptions (from data) ===")
    print(a)
    res = incentive_roi(a)
    print("\n=== Incentive ROI ===")
    for k in ("converted_customers", "total_incentive_spend", "arr_uplift_year_end",
              "npv", "irr", "payback_years", "roi_multiple"):
        print(f"  {k:24s}: {res[k]}")
    print("\n=== Tornado (NPV sensitivity) ===")
    print(tornado(a).to_string(index=False))
