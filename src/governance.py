"""
Governance & data quality.

Three layers a real FP&A data team would insist on before trusting a number:
  1. SCHEMA validation (pandera): types, ranges, categorical domains on the raw CSVs.
  2. REFERENTIAL INTEGRITY: every fact key resolves to a dimension.
  3. RECONCILIATION: the sub-ledger (subscription events) ties to the GL (financials), and the
     ARR roll-forward identity holds.

`build_data_quality_report()` returns plain DataFrames the Streamlit Data-Quality page renders.
`generate_data_dictionary()` writes docs/data_dictionary.md from the live warehouse.
"""
from __future__ import annotations

import os
import warnings

import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pandera as pa
    from pandera import Check, Column, DataFrameSchema

from src import db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")

RECON_TOLERANCE = 0.01  # 1% tolerance for sub-ledger <-> GL reconciliation

# ---------------------------------------------------------------------------
# 1) pandera schemas (the data contract enforced on ingest)
# ---------------------------------------------------------------------------
SEGMENTS = ["SMB", "Commercial", "Enterprise", "Strategic-Global"]
PLATFORMS = ["Strata", "Prisma Cloud", "Cortex", "Identity", "Observability"]
EVENT_TYPES = ["new", "expansion", "contraction", "renewal", "churn",
               "platformization", "inorganic_onboarding"]

SCHEMAS: dict[str, DataFrameSchema] = {
    "dim_customer": DataFrameSchema({
        "customer_id": Column(int, unique=True),
        "segment": Column(str, Check.isin(SEGMENTS)),
        "region": Column(str),
        "industry": Column(str),
        "acquisition_cohort_month": Column(str, Check.str_matches(r"^\d{4}-\d{2}$")),
        "platformized_flag": Column(bool),
        "organic_inorganic": Column(str, Check.isin(["organic", "inorganic"])),
    }, coerce=True, strict=False),

    "dim_platform": DataFrameSchema({
        "platform_id": Column(int, unique=True),
        "platform": Column(str, Check.isin(PLATFORMS)),
        "is_organic": Column(bool),
    }, coerce=True, strict=False),

    "fact_subscription_events": DataFrameSchema({
        "event_id": Column(int, unique=True),
        "month": Column(str, Check.str_matches(r"^\d{4}-\d{2}$")),
        "customer_id": Column(int),
        "platform": Column(str, Check.isin(PLATFORMS)),
        "event_type": Column(str, Check.isin(EVENT_TYPES)),
        "arr_delta": Column(float),
        "acv": Column(float, Check.ge(0)),
        "term_months": Column(int, Check.ge(0)),
    }, coerce=True, strict=False),

    "fact_financials": DataFrameSchema({
        "month": Column(str, Check.str_matches(r"^\d{4}-\d{2}$"), unique=True),
        "total_revenue": Column(float, Check.gt(0)),
        "product_revenue": Column(float, Check.ge(0)),
        "subscription_revenue": Column(float, Check.ge(0)),
        "gross_profit": Column(float, Check.gt(0)),
        "operating_margin": Column(float, Check.in_range(-1, 1)),
        "ngs_arr_total": Column(float, Check.gt(0)),
        "rpo": Column(float, Check.gt(0)),
        "fcf_margin": Column(float, Check.in_range(-1, 1)),
    }, coerce=True, strict=False),

    "fact_threat_signals": DataFrameSchema({
        "month": Column(str, Check.str_matches(r"^\d{4}-\d{2}$"), unique=True),
        "cve_count": Column(int, Check.ge(0)),
        "disclosed_breach_count": Column(int, Check.ge(0)),
        "ai_threat_index": Column(float, Check.ge(0)),
    }, coerce=True, strict=False),
}


def _load_raw(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(RAW, f"{name}.csv"))


def run_schema_checks() -> pd.DataFrame:
    rows = []
    for name, schema in SCHEMAS.items():
        df = _load_raw(name)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                schema.validate(df, lazy=True)
            rows.append({"table": name, "check": "pandera schema", "passed": True,
                         "detail": f"{len(df):,} rows OK"})
        except pa.errors.SchemaErrors as e:
            n = len(e.failure_cases)
            rows.append({"table": name, "check": "pandera schema", "passed": False,
                         "detail": f"{n} failing cases (e.g. {e.failure_cases.iloc[0].to_dict()})"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2) Referential integrity
# ---------------------------------------------------------------------------
def run_referential_integrity() -> pd.DataFrame:
    checks = [
        ("events.customer_id -> dim_customer",
         "SELECT COUNT(*) FROM fact_subscription_events e "
         "LEFT JOIN dim_customer c USING(customer_id) WHERE c.customer_id IS NULL"),
        ("events.platform -> dim_platform",
         "SELECT COUNT(*) FROM fact_subscription_events e "
         "WHERE e.platform NOT IN (SELECT DISTINCT platform FROM dim_platform)"),
        ("events.month -> dim_date",
         "SELECT COUNT(*) FROM fact_subscription_events e "
         "WHERE e.month NOT IN (SELECT date_id FROM dim_date)"),
        ("financials.month -> dim_date",
         "SELECT COUNT(*) FROM fact_financials f "
         "WHERE f.month NOT IN (SELECT date_id FROM dim_date)"),
        ("threat_signals.month -> dim_date",
         "SELECT COUNT(*) FROM fact_threat_signals t "
         "WHERE t.month NOT IN (SELECT date_id FROM dim_date)"),
    ]
    rows = []
    for label, sql in checks:
        v = int(db.query(sql).iloc[0, 0])
        rows.append({"check": label, "passed": v == 0, "violations": v})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3) Reconciliation
# ---------------------------------------------------------------------------
def run_reconciliation() -> pd.DataFrame:
    rows = []

    # (a) ARR roll-forward identity: beginning + motions = ending, every platform-month
    breaks = int(db.query("""
        SELECT COUNT(*) FROM v_arr_rollforward
        WHERE ABS((beginning_arr + new_arr + expansion_arr + platformization_arr
                   + inorganic_arr + contraction_arr + churn_arr) - ending_arr) > 1.0
    """).iloc[0, 0])
    rows.append({"check": "ARR roll-forward identity (per platform-month)",
                 "passed": breaks == 0, "detail": f"{breaks} breaks > $1"})

    # (b) Sub-ledger NGS ARR (event roll-forward) ties to the GL ngs_arr_total
    recon = db.query("""
        SELECT f.month,
               f.ngs_arr_total AS gl_arr,
               s.total_ngs_arr AS subledger_arr
        FROM fact_financials f
        JOIN v_ngs_arr_summary s ON s.month = f.month
    """)
    recon["abs_pct_diff"] = (recon["gl_arr"] - recon["subledger_arr"]).abs() / recon["subledger_arr"]
    worst = recon["abs_pct_diff"].max()
    n_break = int((recon["abs_pct_diff"] > RECON_TOLERANCE).sum())
    rows.append({"check": "Sub-ledger ARR ↔ GL NGS ARR (≤1%)",
                 "passed": n_break == 0,
                 "detail": f"max diff {worst:.4%}, {n_break} months out of tolerance"})

    # (c) P&L coherence: product + subscription = total revenue
    pl = db.query("""
        SELECT COUNT(*) FROM fact_financials
        WHERE ABS((product_revenue + subscription_revenue) - total_revenue) > 1.0
    """).iloc[0, 0]
    rows.append({"check": "Revenue components sum to total",
                 "passed": int(pl) == 0, "detail": f"{int(pl)} months off"})

    # (d) Deferred revenue & RPO strictly positive and monotone-ish (sanity)
    neg = db.query("SELECT COUNT(*) FROM fact_financials WHERE rpo <= 0 OR "
                   "deferred_revenue_current <= 0").iloc[0, 0]
    rows.append({"check": "RPO / deferred revenue positive",
                 "passed": int(neg) == 0, "detail": f"{int(neg)} months non-positive"})

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table profile (counts / null rates)
# ---------------------------------------------------------------------------
def table_profile() -> pd.DataFrame:
    from src.etl import TABLES
    rows = []
    for t in TABLES:
        df = db.table(t)
        null_rate = df.isna().mean()
        rows.append({"table": t, "rows": len(df), "columns": df.shape[1],
                     "max_null_rate": round(float(null_rate.max()), 4),
                     "worst_null_column": null_rate.idxmax() if len(null_rate) else ""})
    return pd.DataFrame(rows)


def build_data_quality_report() -> dict[str, pd.DataFrame]:
    return {
        "profile": table_profile(),
        "schema": run_schema_checks(),
        "referential_integrity": run_referential_integrity(),
        "reconciliation": run_reconciliation(),
    }


def overall_passed(report: dict[str, pd.DataFrame]) -> bool:
    ok = True
    for key in ("schema", "referential_integrity", "reconciliation"):
        ok = ok and bool(report[key]["passed"].all())
    return ok


# ---------------------------------------------------------------------------
# Data dictionary auto-generation
# ---------------------------------------------------------------------------
def generate_data_dictionary(out_path: str | None = None) -> str:
    from src.etl import TABLES
    out_path = out_path or os.path.join(ROOT, "docs", "data_dictionary.md")
    lines = ["# Data Dictionary (auto-generated)\n",
             "_Generated from the live DuckDB warehouse by `src/governance.generate_data_dictionary()`._\n",
             "\n> All data is synthetic — see [assumptions.md](assumptions.md).\n",
             "\n**Lineage:** `data/generate.py` → `data/raw/*.csv` → `src/etl.py` "
             "→ `data/warehouse.duckdb` (tables) → `sql/views.sql` (views) → "
             "`src/*` (metrics & models) → `streamlit_app.py` (app). "
             "Governance (`src/governance.py`) validates the raw CSVs and reconciles the "
             "warehouse.\n"]
    con = db.get_connection()
    try:
        for t in TABLES + ["customer_arr_monthly"]:
            desc = con.execute(f"DESCRIBE {t}").fetchdf()
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            lines.append(f"\n## `{t}`  ({n:,} rows)\n")
            lines.append("| column | type |\n|---|---|")
            for r in desc.itertuples():
                lines.append(f"| {r.column_name} | {r.column_type} |")
            lines.append("")
        # views
        views = con.execute(
            "SELECT view_name FROM duckdb_views() WHERE NOT internal ORDER BY view_name"
        ).fetchdf()
        lines.append("\n## Analytical views (see `sql/views.sql`)\n")
        for v in views["view_name"]:
            lines.append(f"- `{v}`")
    finally:
        con.close()
    text = "\n".join(lines) + "\n"
    with open(out_path, "w") as fh:
        fh.write(text)
    return out_path


if __name__ == "__main__":
    report = build_data_quality_report()
    for name, dfx in report.items():
        print(f"\n=== {name} ===")
        print(dfx.to_string(index=False))
    print(f"\nOVERALL: {'PASS' if overall_passed(report) else 'FAIL'}")
    path = generate_data_dictionary()
    print(f"\nWrote data dictionary -> {path}")
