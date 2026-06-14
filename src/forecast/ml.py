"""
Machine-learning forecaster: gradient-boosted trees (XGBoost) on the monthly net-add flow.

Why ML here: a tree model can pick up non-linear interactions between momentum (recent net-adds),
the fiscal calendar (Q4-heavy bookings), trend, and — optionally — external threat signals
(Option D). It forecasts net-adds recursively (feed each prediction back as the next lag) and we
integrate to an ARR level. The `use_threat` switch powers the Option-D ablation: same model, with
and without the threat features, compared on identical backtest folds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from . import utils

LAGS = [1, 2, 3, 6, 12]
THREAT_COLS = ["cve_count", "disclosed_breach_count", "ai_threat_index"]
THREAT_LAGS = [2, 3]  # the AI-threat index leads bookings by ~2 months


def _calendar(dt: pd.Timestamp) -> dict:
    m = dt.month
    # PANW fiscal-quarter position matters; encode calendar month cyclically + a Q4 flag.
    return {"month_sin": np.sin(2 * np.pi * m / 12), "month_cos": np.cos(2 * np.pi * m / 12),
            "is_fq4": 1.0 if m in (5, 6, 7) else 0.0}


def _row(values: list[float], t: int, dt: pd.Timestamp, threat_df, use_threat, origin) -> dict:
    feat = {f"lag_{L}": values[-L] for L in LAGS}
    feat["roll3"] = np.mean(values[-3:])
    feat["roll12"] = np.mean(values[-12:])
    feat["trend"] = t
    feat.update(_calendar(dt))
    if use_threat and threat_df is not None:
        # LAGGED threat, and only when the lagged month is already OBSERVED at the forecast origin
        # (no leakage). This is exactly the real-world setup: a leading indicator helps the
        # near-term horizon (the next 1-2 months) and goes silent further out. NaNs are fine —
        # XGBoost handles missing features natively.
        for lag in THREAT_LAGS:
            dl = dt - pd.DateOffset(months=lag)
            if dl in threat_df.index and dl <= origin:
                for c in THREAT_COLS:
                    feat[f"{c}_lag{lag}"] = float(threat_df.loc[dl, c])
    return feat


def forecast(history: pd.Series, horizon: int, threat_df: pd.DataFrame | None = None,
             use_threat: bool = False, seed: int = 42) -> pd.Series:
    netadds = utils.to_netadds(history)
    vals = list(netadds.to_numpy())
    dates = list(netadds.index)
    origin = history.index[-1]

    # Build training matrix over the portion where all lags exist.
    X, y = [], []
    start = max(LAGS)
    for i in range(start, len(vals)):
        X.append(_row(vals[:i], i, dates[i], threat_df, use_threat, origin))
        y.append(vals[i])
    Xdf = pd.DataFrame(X)
    model = XGBRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9,
        colsample_bytree=0.9, reg_lambda=1.0, random_state=seed, n_jobs=2)
    model.fit(Xdf, np.asarray(y))

    # Recursive multi-step forecast of net-adds.
    fut_idx = utils.future_index(history, horizon)
    work_vals = list(vals)
    work_dates = list(dates)
    preds = []
    for h, dt in enumerate(fut_idx):
        t = len(work_vals)
        row = _row(work_vals, t, dt, threat_df, use_threat, origin)
        row = pd.DataFrame([row]).reindex(columns=Xdf.columns)
        p = float(model.predict(row)[0])
        preds.append(p)
        work_vals.append(p)
        work_dates.append(dt)
    return utils.integrate(history.iloc[-1], preds, fut_idx)


def feature_importance(history: pd.Series, threat_df=None, use_threat=False, seed=42) -> pd.Series:
    netadds = utils.to_netadds(history)
    vals = list(netadds.to_numpy())
    dates = list(netadds.index)
    origin = history.index[-1]
    X, y = [], []
    for i in range(max(LAGS), len(vals)):
        X.append(_row(vals[:i], i, dates[i], threat_df, use_threat, origin))
        y.append(vals[i])
    Xdf = pd.DataFrame(X)
    model = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                         random_state=seed, n_jobs=2).fit(Xdf, np.asarray(y))
    return pd.Series(model.feature_importances_, index=Xdf.columns).sort_values(ascending=False)
