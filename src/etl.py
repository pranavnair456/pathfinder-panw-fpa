"""
ETL: load the committed raw CSVs into a DuckDB star schema and build the analytical views.

Run:  python src/etl.py     ->  (re)builds data/warehouse.duckdb

The built warehouse is committed so the deployed app needs no build step. Rebuilding is only
necessary after regenerating the data (python data/generate.py).
"""
from __future__ import annotations

import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw")
SQL = os.path.join(ROOT, "sql")
DB_PATH = os.path.join(ROOT, "data", "warehouse.duckdb")

# Tables loaded into the warehouse (file stem -> table name). `_arr_history` is a validation helper.
TABLES = [
    "dim_date", "dim_platform", "dim_customer",
    "fact_subscription_events", "fact_financials", "fact_plan",
    "fact_ma_deals", "fact_threat_signals",
]


def build(db_path: str = DB_PATH) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    con = duckdb.connect(db_path)

    print(f"Loading {len(TABLES)} tables into {db_path} ...")
    for t in TABLES:
        path = os.path.join(RAW, f"{t}.csv")
        # read_csv_auto infers the schema documented in sql/schema.sql; sample_size=-1 = full scan.
        con.execute(
            f"CREATE OR REPLACE TABLE {t} AS "
            f"SELECT * FROM read_csv_auto('{path}', header=true, sample_size=-1)"
        )
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:28s} {n:>8,} rows")

    print("Building analytical views (+ materializing customer_arr_monthly) ...")
    with open(os.path.join(SQL, "views.sql")) as fh:
        con.execute(fh.read())

    _verify(con)
    con.close()
    print(f"Done. Warehouse at {db_path}")


def _verify(con: duckdb.DuckDBPyConnection) -> None:
    """Sanity checks that print right after build (full governance is in src/governance.py)."""
    print("\n=== ETL verification ===")
    # ARR roll-forward ties to the event ledger ending ARR at the latest month
    rf = con.execute("""
        SELECT month, SUM(ending_arr)/1e9 AS total_arr
        FROM v_arr_rollforward
        WHERE month IN ('2025-07','2026-01','2026-04','2026-07')
        GROUP BY month ORDER BY month
    """).fetchall()
    for m, arr in rf:
        print(f"  roll-forward total NGS ARR {m}: ${arr:.2f}B")

    # Roll-forward identity holds for every platform-month:
    #   beginning + new + expansion + platformization + inorganic + contraction + churn = ending
    broken = con.execute("""
        SELECT COUNT(*) FROM v_arr_rollforward
        WHERE ABS((beginning_arr + new_arr + expansion_arr + platformization_arr
                   + inorganic_arr + contraction_arr + churn_arr) - ending_arr) > 1.0
    """).fetchone()[0]
    print(f"  roll-forward identity breaks (tol $1): {broken}  (expect 0)")

    nrr = con.execute("SELECT nrr, grr, logo_retention FROM v_nrr_grr "
                      "WHERE month='2026-04'").fetchone()
    if nrr:
        print(f"  NRR/GRR/logo @2026-04: {nrr[0]:.3f} / {nrr[1]:.3f} / {nrr[2]:.3f}")

    plat = con.execute("""
        SELECT platformized_flag, ROUND(nrr,3) FROM v_nrr_by_platformization
        WHERE month='2026-04' ORDER BY platformized_flag
    """).fetchall()
    print(f"  NRR by platformization @2026-04: {plat}")


if __name__ == "__main__":
    build()
