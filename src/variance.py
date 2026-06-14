"""
Variance analysis: actual vs plan, and the ARR roll-forward waterfall ("bridge").

Two FP&A staples:
  - QUARTERLY VARIANCE: actual vs board-approved plan for NGS ARR, revenue and operating margin,
    in dollars and percent — the "are we on plan?" table.
  - ARR BRIDGE: how beginning ARR became ending ARR through new / expansion / platformization /
    inorganic / contraction / churn — the waterfall a CFO reads to see *why* ARR moved.

The biggest variances feed the LLM narrative hook in src/narrative.py.
"""
from __future__ import annotations

import pandas as pd

from src import db

MOTION_ORDER = ["beginning_arr", "new_arr", "expansion_arr", "platformization_arr",
                "inorganic_arr", "contraction_arr", "churn_arr", "ending_arr"]
MOTION_LABELS = {
    "beginning_arr": "Beginning ARR", "new_arr": "New", "expansion_arr": "Expansion",
    "platformization_arr": "Platformization", "inorganic_arr": "Inorganic (M&A)",
    "contraction_arr": "Contraction", "churn_arr": "Churn", "ending_arr": "Ending ARR",
}


def quarterly_variance() -> pd.DataFrame:
    """Per fiscal quarter: actual vs plan for NGS ARR (quarter-end), revenue (sum), op margin (avg)."""
    df = db.query("""
        WITH q AS (
            SELECT fiscal_year, fiscal_quarter, month,
                   actual_ngs_arr, plan_ngs_arr, actual_revenue, plan_revenue,
                   actual_op_margin, plan_op_margin,
                   ROW_NUMBER() OVER (PARTITION BY fiscal_year, fiscal_quarter
                                      ORDER BY month DESC) AS rn_end
            FROM v_actual_vs_plan
        )
        SELECT fiscal_year, fiscal_quarter, MAX(month) AS quarter_end_month,
               MAX(CASE WHEN rn_end=1 THEN actual_ngs_arr END) AS actual_ngs_arr,
               MAX(CASE WHEN rn_end=1 THEN plan_ngs_arr   END) AS plan_ngs_arr,
               SUM(actual_revenue) AS actual_revenue,
               SUM(plan_revenue)   AS plan_revenue,
               AVG(actual_op_margin) AS actual_op_margin,
               AVG(plan_op_margin)   AS plan_op_margin
        FROM q GROUP BY fiscal_year, fiscal_quarter
        ORDER BY fiscal_year, fiscal_quarter
    """)
    df["ngs_arr_var"] = df["actual_ngs_arr"] - df["plan_ngs_arr"]
    df["ngs_arr_var_pct"] = df["ngs_arr_var"] / df["plan_ngs_arr"]
    df["revenue_var"] = df["actual_revenue"] - df["plan_revenue"]
    df["revenue_var_pct"] = df["revenue_var"] / df["plan_revenue"]
    df["op_margin_var_bps"] = (df["actual_op_margin"] - df["plan_op_margin"]) * 10000
    return df


def arr_bridge(fiscal_year: str | None = None, fiscal_quarter: str | None = None) -> pd.DataFrame:
    """ARR roll-forward waterfall for a fiscal quarter (defaults to the latest actual quarter)."""
    fy_fq = db.query("""
        SELECT d.fiscal_year, d.fiscal_quarter
        FROM v_arr_rollforward r JOIN dim_date d ON d.date_id = r.month
        WHERE d.is_history GROUP BY 1,2 ORDER BY MAX(r.month) DESC LIMIT 1
    """)
    fy = fiscal_year or int(fy_fq.iloc[0, 0])
    fq = fiscal_quarter or int(fy_fq.iloc[0, 1])
    rows = db.query("""
        WITH motions AS (
            SELECT r.month,
                   SUM(r.new_arr) new_arr, SUM(r.expansion_arr) expansion_arr,
                   SUM(r.platformization_arr) platformization_arr, SUM(r.inorganic_arr) inorganic_arr,
                   SUM(r.contraction_arr) contraction_arr, SUM(r.churn_arr) churn_arr,
                   SUM(r.beginning_arr) beginning_arr, SUM(r.ending_arr) ending_arr
            FROM v_arr_rollforward r JOIN dim_date d ON d.date_id = r.month
            WHERE d.fiscal_year = ? AND d.fiscal_quarter = ?
            GROUP BY r.month
        )
        SELECT
            (SELECT beginning_arr FROM motions ORDER BY month LIMIT 1) AS beginning_arr,
            SUM(new_arr) AS new_arr, SUM(expansion_arr) AS expansion_arr,
            SUM(platformization_arr) AS platformization_arr, SUM(inorganic_arr) AS inorganic_arr,
            SUM(contraction_arr) AS contraction_arr, SUM(churn_arr) AS churn_arr,
            (SELECT ending_arr FROM motions ORDER BY month DESC LIMIT 1) AS ending_arr
        FROM motions
    """, [int(fy), int(fq)]).iloc[0]
    out = pd.DataFrame({"motion": [MOTION_LABELS[m] for m in MOTION_ORDER],
                        "key": MOTION_ORDER,
                        "value": [float(rows[m]) for m in MOTION_ORDER]})
    out.attrs["fiscal_year"], out.attrs["fiscal_quarter"] = f"FY{fy}", f"Q{fq}"
    return out


def variance_highlights(n: int = 3) -> dict:
    """Structured facts the narrative module turns into prose."""
    qv = quarterly_variance().dropna(subset=["actual_ngs_arr"])
    latest = qv.iloc[-1]
    bridge = arr_bridge()
    motions = {r.key: r.value for r in bridge.itertuples()}
    return {
        "fiscal_period": f"{latest['fiscal_year']}-{latest['fiscal_quarter']}",
        "actual_ngs_arr": float(latest["actual_ngs_arr"]),
        "plan_ngs_arr": float(latest["plan_ngs_arr"]),
        "ngs_arr_var": float(latest["ngs_arr_var"]),
        "ngs_arr_var_pct": float(latest["ngs_arr_var_pct"]),
        "revenue_var_pct": float(latest["revenue_var_pct"]),
        "op_margin_var_bps": float(latest["op_margin_var_bps"]),
        "bridge": {k: float(v) for k, v in motions.items()},
    }


if __name__ == "__main__":
    print("=== Quarterly variance (last 4) ===")
    print(quarterly_variance().tail(4)[
        ["fiscal_year", "fiscal_quarter", "actual_ngs_arr", "plan_ngs_arr",
         "ngs_arr_var_pct", "revenue_var_pct", "op_margin_var_bps"]].to_string(index=False))
    print("\n=== ARR bridge (latest quarter) ===")
    b = arr_bridge()
    print(f"{b.attrs['fiscal_year']}-{b.attrs['fiscal_quarter']}")
    print(b[["motion", "value"]].to_string(index=False))
