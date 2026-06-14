"""
Shared forecasting utilities: target-series loaders, error metrics, and net-add helpers.

Modeling note — why we forecast ORGANIC NGS ARR:
    Total NGS ARR contains a known *step change* when CyberArk and Chronosphere close (Jan-Feb
    2026). Asking a statistical model to "predict" an M&A close is meaningless — those dollars are
    contractual, not forecastable. So the forecasting models target the smooth ORGANIC series; the
    inorganic ramp is layered back on in trajectory.py (and modeled explicitly in src/ma.py). This
    is exactly how an FP&A team separates organic momentum from inorganic step-ups.

Most models work on the monthly NET-ADD flow (organic ARR added each month) rather than the ARR
level, because the flow carries the seasonality (PANW's fiscal-Q4-heavy bookings) and is far less
trended — which is what a seasonal-naive baseline and ARIMA-type models expect. We then integrate
the flow back into an ARR level.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import db

SEASON = 12  # months


# ---------------------------------------------------------------------------
# Target series
# ---------------------------------------------------------------------------
def _to_series(df: pd.DataFrame, col: str) -> pd.Series:
    s = df.copy()
    s["ts"] = pd.to_datetime(s["month"] + "-01")
    s = s.set_index("ts")[col].astype(float).sort_index()
    s.index.freq = "MS"
    return s


def load_organic_ngs_arr() -> pd.Series:
    """Monthly ORGANIC NGS ARR level ($), the primary forecasting target."""
    df = db.query("SELECT month, organic_ngs_arr FROM v_ngs_arr_summary ORDER BY month")
    return _to_series(df, "organic_ngs_arr")


def load_total_ngs_arr() -> pd.Series:
    df = db.query("SELECT month, total_ngs_arr FROM v_ngs_arr_summary ORDER BY month")
    return _to_series(df, "total_ngs_arr")


def load_threat_features() -> pd.DataFrame:
    """Threat signals indexed by month-start (for the ML feature layer / Option D)."""
    df = db.query("SELECT * FROM fact_threat_signals ORDER BY month")
    df["ts"] = pd.to_datetime(df["month"] + "-01")
    return df.set_index("ts").drop(columns=["month"])


# ---------------------------------------------------------------------------
# Net-add helpers (level <-> flow)
# ---------------------------------------------------------------------------
def to_netadds(level: pd.Series) -> pd.Series:
    """First difference of the ARR level = monthly net new ARR (the flow)."""
    return level.diff().dropna()


def integrate(last_level: float, netadds: list[float] | np.ndarray, index: pd.DatetimeIndex
              ) -> pd.Series:
    """Cumulate a sequence of net-adds onto a starting level -> forecast ARR level series."""
    return pd.Series(last_level + np.cumsum(netadds), index=index)


def future_index(history: pd.Series, horizon: int) -> pd.DatetimeIndex:
    start = history.index[-1] + pd.offsets.MonthBegin(1)
    return pd.date_range(start=start, periods=horizon, freq="MS")


# ---------------------------------------------------------------------------
# Error metrics
# ---------------------------------------------------------------------------
def wape(actual, forecast) -> float:
    """Weighted Absolute Percentage Error = sum|e| / sum|actual|. Robust for large-level series."""
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.sum(np.abs(actual - forecast)) / (np.sum(np.abs(actual)) + 1e-9))


def mape(actual, forecast) -> float:
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.mean(np.abs((actual - forecast) / (actual + 1e-9))))


def rmse(actual, forecast) -> float:
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.sqrt(np.mean((actual - forecast) ** 2)))


def smape(actual, forecast) -> float:
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.mean(2 * np.abs(actual - forecast) / (np.abs(actual) + np.abs(forecast) + 1e-9)))


def all_metrics(actual, forecast) -> dict:
    return {"WAPE": wape(actual, forecast), "MAPE": mape(actual, forecast),
            "RMSE": rmse(actual, forecast), "sMAPE": smape(actual, forecast)}
