"""
Rolling-origin backtesting and model comparison.

Honest evaluation: for several expanding-window cutoffs we train on the past, forecast a fixed
horizon, and score against the held-out actuals (WAPE / MAPE / RMSE / sMAPE). The headline is
'skill vs seasonal-naive' — how much each model beats the baseline. A model that can't beat the
baseline doesn't ship. Results are cached to data/backtest_results.json so the app and model card
read them without re-running the grid search.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from . import baseline, classical, driver_based, ml, utils

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "data", "backtest_results.json")

_THREAT = None


def _threat():
    global _THREAT
    if _THREAT is None:
        _THREAT = utils.load_threat_features()
    return _THREAT


MODELS = {
    "Seasonal-Naive": baseline.seasonal_naive,
    "Naive-Drift": baseline.naive_drift,
    "Seasonal-Naive + Drift": baseline.seasonal_naive_drift,
    "ETS (Holt-Winters)": classical.ets,
    "Auto-ARIMA": classical.auto_arima,
    "XGBoost": ml.forecast,
    "XGBoost + Threat": lambda h, horizon: ml.forecast(
        h, horizon, threat_df=_threat(), use_threat=True),
    "Driver-Based": driver_based.forecast,
}
BASELINE = "Seasonal-Naive"


def rolling_origin(series: pd.Series, horizon: int = 6, min_train: int = 48, step: int = 3
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-fold metrics, per-model summary). Expanding window."""
    cutoffs = list(range(min_train, len(series) - horizon + 1, step))
    rows = []
    for name, fn in MODELS.items():
        for c in cutoffs:
            train, test = series.iloc[:c], series.iloc[c:c + horizon]
            try:
                fc = fn(train, horizon).reindex(test.index)
                # Level metrics (what stakeholders read) AND flow metrics (the discriminating part:
                # the ARR base dwarfs monthly motion, so level WAPE is ~uninformative).
                prev = train.iloc[-1]
                act_flow = np.diff(np.r_[prev, test.to_numpy()])
                fc_flow = np.diff(np.r_[prev, fc.to_numpy()])
                m = {f"level_{k}": v for k, v in utils.all_metrics(test, fc).items()}
                m.update({f"flow_{k}": v for k, v in utils.all_metrics(act_flow, fc_flow).items()})
                m.update({"model": name, "cutoff": series.index[c - 1].strftime("%Y-%m")})
                rows.append(m)
            except Exception as e:  # noqa: BLE001 — a failed fit shouldn't kill the comparison
                rows.append({"model": name, "cutoff": series.index[c - 1].strftime("%Y-%m"),
                             "error": str(e)[:80]})
    per_fold = pd.DataFrame(rows)
    metric_cols = ["level_WAPE", "level_RMSE", "flow_WAPE", "flow_MAPE", "flow_RMSE", "flow_sMAPE"]
    metric_cols = [c for c in metric_cols if c in per_fold.columns]
    summary = per_fold.groupby("model")[metric_cols].mean().reset_index()
    base = float(summary.loc[summary["model"] == BASELINE, "flow_WAPE"].iloc[0])
    summary["skill_vs_baseline_%"] = (1 - summary["flow_WAPE"] / base) * 100
    summary = summary.sort_values("flow_WAPE").reset_index(drop=True)
    return per_fold, summary


def choose_best(summary: pd.DataFrame) -> str:
    """Best skill on the flow (net-new ARR) wins — the part that's actually hard to predict."""
    return summary.sort_values(["flow_WAPE", "level_WAPE"]).iloc[0]["model"]


def run_and_cache(horizon: int = 6, min_train: int = 42, step: int = 3) -> dict:
    series = utils.load_organic_ngs_arr()
    per_fold, summary = rolling_origin(series, horizon=horizon, min_train=min_train, step=step)
    best = choose_best(summary)
    payload = {
        "horizon": horizon,
        "n_folds": int(per_fold["cutoff"].nunique()),
        "best_model": best,
        "summary": summary.to_dict(orient="records"),
        "per_fold": per_fold.to_dict(orient="records"),
        "generated_for_series_end": series.index[-1].strftime("%Y-%m"),
    }
    with open(CACHE, "w") as fh:
        json.dump(payload, fh, indent=2, default=float)
    return payload


def load_cached() -> dict | None:
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            return json.load(fh)
    return None


if __name__ == "__main__":
    p = run_and_cache()
    print(f"Folds: {p['n_folds']} | horizon {p['horizon']}m | best model: {p['best_model']}\n")
    print(pd.DataFrame(p["summary"]).to_string(index=False))
