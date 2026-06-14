"""
Tiny read-only DuckDB access layer shared by the metrics/forecast/app modules.

Keeping a single accessor means the Streamlit app can wrap `query()` in @st.cache_data and every
module talks to the warehouse the same way.
"""
from __future__ import annotations

import os

import duckdb
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "warehouse.duckdb")


def get_connection(db_path: str = DB_PATH, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Warehouse not found at {db_path}. Build it with `python src/etl.py` "
            "(after `python data/generate.py` if the raw CSVs are missing)."
        )
    return duckdb.connect(db_path, read_only=read_only)


def query(sql: str, params: list | None = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Run a SQL query against the warehouse and return a DataFrame."""
    con = get_connection(db_path)
    try:
        return con.execute(sql, params or []).fetchdf()
    finally:
        con.close()


def table(name: str, db_path: str = DB_PATH) -> pd.DataFrame:
    return query(f"SELECT * FROM {name}", db_path=db_path)
