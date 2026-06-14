"""
Option D — Threat-signal demand layer.

Hypothesis: external cyber-threat activity (CVE volume, disclosed breaches, an "AI-threat index"
echoing PANW's "AI is weaponizing attacks" thesis) LEADS security demand, so it should improve a
near-term NGS-ARR forecast. We test it honestly:

  1. Lagged cross-correlation — at what lead does the AI-threat index line up with organic net-adds?
  2. Ablation — the SAME XGBoost model, 1-step-ahead rolling backtest, WITH vs WITHOUT the lagged
     threat features. The lift (or lack of it) is reported as-is.

Why 1-step / near-term: a leading indicator can only help while its lead is still *observed*. At
the forecast origin you know threat up to today; with a ~2-month lead it informs the next 1-2
months and then goes silent. So the honest place to look for lift is the near term — not the
multi-year $20B trajectory (which it cannot help, and we say so).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from src.forecast import baseline, ml, utils

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "threat_ablation.json")


def load_signals() -> pd.DataFrame:
    return utils.load_threat_features()


def organic_netadds() -> pd.Series:
    return utils.to_netadds(utils.load_organic_ngs_arr())


def lagged_correlation(max_lag: int = 6) -> pd.DataFrame:
    """corr( threat_index[t-lag], organic_netadds[t] ) for lag = 0..max_lag. Peak = the lead."""
    sig = load_signals()["ai_threat_index"]
    na = organic_netadds()
    df = pd.concat([sig.rename("threat"), na.rename("netadds")], axis=1).dropna()
    rows = []
    for lag in range(max_lag + 1):
        c = df["threat"].shift(lag).corr(df["netadds"])
        rows.append({"lead_months": lag, "correlation": float(c)})
    return pd.DataFrame(rows)


def ablation(min_train: int = 48, n_folds: int | None = None, seed: int = 42) -> dict:
    """1-step-ahead rolling backtest of net-adds: XGBoost WITH vs WITHOUT lagged threat features.

    Also reports the seasonal-naive 1-step error as a reference point.
    """
    series = utils.load_organic_ngs_arr()
    threat = load_signals()
    cutoffs = list(range(min_train, len(series) - 1))
    if n_folds:
        cutoffs = cutoffs[-n_folds:]

    rows = []
    for c in cutoffs:
        train = series.iloc[:c]
        actual_level = series.iloc[c]
        actual_add = actual_level - train.iloc[-1]
        fc_no = ml.forecast(train, 1, use_threat=False, seed=seed).iloc[0] - train.iloc[-1]
        fc_yes = ml.forecast(train, 1, threat_df=threat, use_threat=True, seed=seed).iloc[0] \
            - train.iloc[-1]
        fc_sn = baseline.seasonal_naive(train, 1).iloc[0] - train.iloc[-1]
        rows.append({"cutoff": series.index[c - 1].strftime("%Y-%m"),
                     "actual_add": actual_add, "no_threat": fc_no,
                     "with_threat": fc_yes, "seasonal_naive": fc_sn})
    fold = pd.DataFrame(rows)

    def _wape(col):
        return float(np.sum(np.abs(fold["actual_add"] - fold[col]))
                     / (np.sum(np.abs(fold["actual_add"])) + 1e-9))

    wape_no, wape_yes, wape_sn = _wape("no_threat"), _wape("with_threat"), _wape("seasonal_naive")
    lift = (1 - wape_yes / wape_no) * 100 if wape_no else 0.0
    return {
        "n_folds": len(fold),
        "wape_no_threat": wape_no,
        "wape_with_threat": wape_yes,
        "wape_seasonal_naive": wape_sn,
        "threat_lift_pct": lift,                      # >0 => threat helped
        "threat_helps": wape_yes < wape_no,
        "beats_seasonal_naive": wape_yes < wape_sn,
        "per_fold": fold,
    }


def feature_importance_with_threat() -> pd.Series:
    return ml.feature_importance(utils.load_organic_ngs_arr(),
                                 threat_df=load_signals(), use_threat=True)


def summary_text(abl: dict) -> str:
    direction = "improves" if abl["threat_helps"] else "does NOT improve"
    return (
        f"Over {abl['n_folds']} one-step folds, adding lagged threat features {direction} the "
        f"XGBoost net-add forecast: WAPE {abl['wape_no_threat']:.3f} (no threat) -> "
        f"{abl['wape_with_threat']:.3f} (with threat), a lift of {abl['threat_lift_pct']:.1f}%. "
        f"Reference seasonal-naive WAPE = {abl['wape_seasonal_naive']:.3f}."
    )


def run_and_cache() -> dict:
    corr = lagged_correlation()
    abl = ablation()
    payload = {
        "correlation": corr.to_dict(orient="records"),
        "ablation": {k: v for k, v in abl.items() if k != "per_fold"},
        "per_fold": abl["per_fold"].to_dict(orient="records"),
        "feature_importance": feature_importance_with_threat().round(4).to_dict(),
        "summary": summary_text(abl),
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
    print("=== Lagged correlation (threat lead vs organic net-adds) ===")
    print(lagged_correlation().to_string(index=False))
    abl = ablation()
    print("\n=== Ablation: threat feature lift (1-step) ===")
    for k in ("n_folds", "wape_no_threat", "wape_with_threat", "wape_seasonal_naive",
              "threat_lift_pct", "threat_helps", "beats_seasonal_naive"):
        print(f"  {k:22s}: {abl[k]}")
    print("\n" + summary_text(abl))
