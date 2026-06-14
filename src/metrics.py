"""
Core SaaS / FP&A metrics.

Thin Python layer over the SQL views (src/db.py). The SQL does the heavy ARR / retention math;
here we add the derived KPIs that combine the ledger with the GL — ARPU, CAC, LTV, Rule of 40,
and the SaaS magic number — and assemble the executive KPI snapshot.

Every metric carries a docstring explaining the FINANCIAL reasoning, because the point of this
project is to teach the domain, not just compute it. See docs/finance_concepts.md for the long form.
"""
from __future__ import annotations

import pandas as pd

from src import db

# Modeling assumptions for the derived unit economics (documented in docs/methodology.md).
SM_ACQUISITION_SHARE = 0.65   # share of S&M spend attributed to NEW-logo acquisition (vs retain/expand)
GROSS_MARGIN_NONGAAP = 0.765  # for LTV contribution margin


# ---------------------------------------------------------------------------
# Pass-through accessors to the SQL views
# ---------------------------------------------------------------------------
def ngs_arr_summary() -> pd.DataFrame:
    """Monthly total NGS ARR with organic vs inorganic split."""
    return db.query("SELECT * FROM v_ngs_arr_summary ORDER BY month")


def arr_by_platform() -> pd.DataFrame:
    return db.query("SELECT * FROM v_ngs_arr_by_platform ORDER BY month, platform")


def arr_rollforward(platform: str | None = None) -> pd.DataFrame:
    if platform:
        return db.query("SELECT * FROM v_arr_rollforward WHERE platform = ? ORDER BY month",
                        [platform])
    return db.query("SELECT * FROM v_arr_rollforward ORDER BY platform, month")


def arr_rollforward_total() -> pd.DataFrame:
    """Company-wide ARR bridge: sum the per-platform motions by month."""
    return db.query("""
        SELECT month,
               SUM(beginning_arr) AS beginning_arr,
               SUM(new_arr) AS new_arr,
               SUM(expansion_arr) AS expansion_arr,
               SUM(platformization_arr) AS platformization_arr,
               SUM(inorganic_arr) AS inorganic_arr,
               SUM(contraction_arr) AS contraction_arr,
               SUM(churn_arr) AS churn_arr,
               SUM(ending_arr) AS ending_arr
        FROM v_arr_rollforward GROUP BY month ORDER BY month
    """)


def nrr_grr() -> pd.DataFrame:
    """Net & Gross Revenue Retention (trailing-12m). NRR>100% = the existing base alone grows."""
    return db.query("SELECT * FROM v_nrr_grr ORDER BY month")


def nrr_by_platformization() -> pd.DataFrame:
    return db.query("SELECT * FROM v_nrr_by_platformization ORDER BY month, platformized_flag")


def cohort_retention() -> pd.DataFrame:
    return db.query("SELECT * FROM v_cohort_retention")


def rpo_deferred() -> pd.DataFrame:
    return db.query("SELECT * FROM v_rpo_deferred ORDER BY month")


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------
def active_customers() -> pd.DataFrame:
    """Count of customers with positive ARR each month (the live logo base)."""
    return db.query("""
        SELECT month, COUNT(*) FILTER (WHERE arr > 0) AS active_customers
        FROM customer_arr_monthly GROUP BY month ORDER BY month
    """)


def arpu() -> pd.DataFrame:
    """ARPU = total NGS ARR / active customers. Rising ARPU = up-market / platformization mix."""
    arr = ngs_arr_summary()[["month", "total_ngs_arr"]]
    ac = active_customers()
    df = arr.merge(ac, on="month")
    df["arpu"] = df["total_ngs_arr"] / df["active_customers"]
    return df


def _quarterly_financials() -> pd.DataFrame:
    """Aggregate the monthly GL to fiscal quarters (revenue/S&M/FCF summed, ARR = quarter-end)."""
    return db.query("""
        WITH q AS (
            SELECT fiscal_year, fiscal_quarter, month,
                   total_revenue, sales_marketing, adjusted_free_cash_flow, ngs_arr_total,
                   ROW_NUMBER() OVER (PARTITION BY fiscal_year, fiscal_quarter
                                      ORDER BY month DESC) AS rn_end
            FROM fact_financials
        )
        SELECT fiscal_year, fiscal_quarter,
               MAX(month) AS quarter_end_month,
               SUM(total_revenue) AS revenue,
               SUM(sales_marketing) AS sales_marketing,
               SUM(adjusted_free_cash_flow) AS adj_fcf,
               MAX(CASE WHEN rn_end = 1 THEN ngs_arr_total END) AS ngs_arr_end
        FROM q GROUP BY fiscal_year, fiscal_quarter
        ORDER BY fiscal_year, fiscal_quarter
    """)


def rule_of_40() -> pd.DataFrame:
    """Rule of 40: YoY revenue growth % + adjusted FCF margin %. >40 = healthy SaaS.

    Trades off growth against profitability — a company can 'pass' by growing fast OR by being
    very profitable. PANW's pitch is doing both as it scales.
    """
    q = _quarterly_financials()
    q["fcf_margin"] = q["adj_fcf"] / q["revenue"]
    q["rev_yoy"] = q["revenue"] / q["revenue"].shift(4) - 1
    q["rule_of_40"] = (q["rev_yoy"] + q["fcf_margin"]) * 100
    return q.dropna(subset=["rev_yoy"])[
        ["fiscal_year", "fiscal_quarter", "quarter_end_month", "rev_yoy", "fcf_margin", "rule_of_40"]
    ]


def magic_number() -> pd.DataFrame:
    """SaaS magic number = net-new NGS ARR in quarter / prior-quarter S&M spend.

    A capital-efficiency gauge: >0.75 means each $1 of S&M is buying back >$0.75 of new ARR — i.e.
    sales & marketing is paying off. Uses ARR (already annualized) rather than ×4 quarterly revenue.
    """
    q = _quarterly_financials()
    q["net_new_arr"] = q["ngs_arr_end"] - q["ngs_arr_end"].shift(1)
    q["prior_sm"] = q["sales_marketing"].shift(1)
    q["magic_number"] = q["net_new_arr"] / q["prior_sm"]
    return q.dropna(subset=["magic_number"])[
        ["fiscal_year", "fiscal_quarter", "quarter_end_month", "net_new_arr", "prior_sm", "magic_number"]
    ]


def unit_economics() -> pd.DataFrame:
    """CAC, LTV and LTV/CAC by fiscal quarter (approximate; see SM_ACQUISITION_SHARE assumption).

    CAC  = (S&M × acquisition share) / new logos won that quarter.
    LTV  = annual ARPU × gross margin × expected lifetime, with lifetime = 1 / annual gross churn
           (annual gross churn ≈ 1 − GRR). LTV/CAC > 3 is the classic 'efficient growth' bar.
    """
    # new logos per fiscal quarter (first-ever event per customer = their cohort)
    logos = db.query("""
        SELECT 'FY' || d.fiscal_year AS fiscal_year,
               'Q' || d.fiscal_quarter AS fiscal_quarter,
               COUNT(*) AS new_logos
        FROM dim_customer c
        JOIN dim_date d ON d.date_id = c.acquisition_cohort_month
        GROUP BY d.fiscal_year, d.fiscal_quarter
    """)
    q = _quarterly_financials().merge(logos, on=["fiscal_year", "fiscal_quarter"], how="left")
    q["new_logos"] = q["new_logos"].fillna(0)

    # annual gross churn from the latest available GRR (fallback 0.07)
    grr = nrr_grr()
    annual_gross_churn = max(1 - float(grr["grr"].iloc[-1]), 0.02) if len(grr) else 0.07

    ac = active_customers()
    ac["fy_q_end"] = ac["month"]
    q = q.merge(ac[["month", "active_customers"]],
                left_on="quarter_end_month", right_on="month", how="left")
    q["arpu_annual"] = q["ngs_arr_end"] / q["active_customers"]
    q["cac"] = (q["sales_marketing"] * SM_ACQUISITION_SHARE) / q["new_logos"].replace(0, pd.NA)
    # Cap modeled customer lifetime at 10 years: 1/churn overstates LTV at very high GRR, and
    # finance convention bounds the horizon (technology/refresh risk). See methodology.md.
    q["lifetime_years"] = min(1 / annual_gross_churn, 10.0)
    q["ltv"] = q["arpu_annual"] * GROSS_MARGIN_NONGAAP * q["lifetime_years"]
    q["ltv_cac"] = q["ltv"] / q["cac"]
    return q[["fiscal_year", "fiscal_quarter", "quarter_end_month", "new_logos",
              "cac", "arpu_annual", "lifetime_years", "ltv", "ltv_cac"]]


def platformized_count() -> pd.DataFrame:
    """Count of platformized customers as of each quarter-end (toward the 4,000+ FY2030 target)."""
    return db.query("""
        WITH qe AS (
            SELECT DISTINCT fiscal_year, fiscal_quarter, date_id AS quarter_end_month
            FROM dim_date WHERE is_history AND is_quarter_end_month
        )
        SELECT qe.fiscal_year, qe.fiscal_quarter, qe.quarter_end_month,
               COUNT(c.customer_id) AS platformized
        FROM qe
        LEFT JOIN dim_customer c
               ON c.platformized_flag
              AND c.platformization_date <= qe.quarter_end_month
        GROUP BY qe.fiscal_year, qe.fiscal_quarter, qe.quarter_end_month
        ORDER BY qe.fiscal_year, qe.fiscal_quarter
    """)


# ---------------------------------------------------------------------------
# Executive KPI snapshot
# ---------------------------------------------------------------------------
def kpi_snapshot(month: str | None = None) -> dict:
    """Headline KPIs for the Executive Summary page, as of `month` (default = latest actual)."""
    arr = ngs_arr_summary()
    if month is None:
        month = arr["month"].iloc[-1]
    row = arr[arr["month"] == month].iloc[0]
    yoy_month = arr[arr["month"] <= month].iloc[-13] if len(arr) >= 13 else arr.iloc[0]
    yoy = float(row["total_ngs_arr"] / yoy_month["total_ngs_arr"] - 1)

    fin = db.query("SELECT * FROM fact_financials WHERE month = ?", [month]).iloc[0]
    nrr = nrr_grr()
    nrr_now = float(nrr[nrr["month"] == month]["nrr"].iloc[0]) if month in nrr["month"].values \
        else float(nrr["nrr"].iloc[-1])
    r40 = rule_of_40()
    r40_now = float(r40["rule_of_40"].iloc[-1]) if len(r40) else float("nan")
    plat = platformized_count()
    plat_now = int(plat["platformized"].iloc[-1]) if len(plat) else 0

    return {
        "month": month,
        "ngs_arr": float(row["total_ngs_arr"]),
        "ngs_arr_organic": float(row["organic_ngs_arr"]),
        "ngs_arr_inorganic": float(row["inorganic_ngs_arr"]),
        "ngs_arr_yoy": yoy,
        "nrr": nrr_now,
        "rule_of_40": r40_now,
        "fcf_margin": float(fin["fcf_margin"]),
        "operating_margin": float(fin["operating_margin"]),
        "rpo": float(fin["rpo"]),
        "revenue_month": float(fin["total_revenue"]),
        "platformized": plat_now,
        "progress_to_20b": float(row["total_ngs_arr"] / 20e9),
    }


if __name__ == "__main__":
    snap = kpi_snapshot()
    print("=== Executive KPI snapshot ===")
    for k, v in snap.items():
        print(f"  {k:20s}: {v}")
    print("\n=== Rule of 40 (last 4) ===")
    print(rule_of_40().tail(4).to_string(index=False))
    print("\n=== Magic number (last 4) ===")
    print(magic_number().tail(4).to_string(index=False))
    print("\n=== Unit economics (last 4) ===")
    print(unit_economics().tail(4).to_string(index=False))
