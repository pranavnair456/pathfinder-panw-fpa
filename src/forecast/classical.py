"""
Classical statistical forecasters: Holt-Winters (ETS) and SARIMA via a custom auto-ARIMA grid.

We model on the LOG of the ARR level so multiplicative growth becomes additive (constant % growth
-> straight line), which suits ARIMA/ETS assumptions. We deliberately use statsmodels + a small
order grid instead of pmdarima/prophet (fragile/heavy on py3.12 + Streamlit Cloud); the grid also
makes the model-selection logic explicit. See docs/model_card.md.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.statespace.sarimax import SARIMAX

from . import utils


def ets(history: pd.Series, horizon: int, seasonal_periods: int = 12) -> pd.Series:
    """Holt-Winters with damped additive TREND + MULTIPLICATIVE seasonality (period 12).

    The textbook model for a growing, seasonal series: multiplicative seasonality lets the
    fiscal-Q4 booking spike scale up with the ARR base, while the damped trend captures the gentle
    growth deceleration. It captures BOTH signals — which is why it beats seasonal-naive (trend-
    blind) and naive-drift (seasonality-blind). Falls back to damped-trend-only if the fit fails.
    """
    idx = utils.future_index(history, horizon)

    def _damped_log():
        logy = np.log(history)
        m = ExponentialSmoothing(logy, trend="add", damped_trend=True,
                                 seasonal=None, initialization_method="estimated").fit()
        return pd.Series(np.exp(np.asarray(m.forecast(horizon))), index=idx)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model = ExponentialSmoothing(
                history, trend="add", damped_trend=True, seasonal="mul",
                seasonal_periods=seasonal_periods, initialization_method="estimated").fit()
            fc = np.asarray(model.forecast(horizon), dtype=float)
            # Guard against the known HW multiplicative blow-up: sanity-check the path.
            if (not np.all(np.isfinite(fc)) or np.any(fc <= 0)
                    or fc.max() > history.iloc[-1] * 3):
                return _damped_log()
            return pd.Series(fc, index=idx)
        except Exception:
            return _damped_log()


def _fit_sarimax(logy, order, seasonal_order):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return SARIMAX(logy, order=order, seasonal_order=seasonal_order,
                       enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)


def auto_arima(history: pd.Series, horizon: int, return_model: bool = False):
    """Small AIC-minimizing grid search over (S)ARIMA orders on log ARR.

    Grid kept compact for speed/robustness; seasonal terms (period 12) optional. Returns the ARR
    level point forecast (and, if return_model, the fitted result for prediction intervals).
    """
    logy = np.log(history)
    p_grid, d_grid, q_grid = (0, 1, 2), (1, 2), (0, 1, 2)
    seasonal_grid = [(0, 0, 0, 0), (1, 0, 0, 12), (0, 1, 1, 12)]
    best = (np.inf, None, None, None)
    for d in d_grid:
        for p in p_grid:
            for q in q_grid:
                for so in seasonal_grid:
                    try:
                        res = _fit_sarimax(logy, (p, d, q), so)
                        if res.aic < best[0]:
                            best = (res.aic, (p, d, q), so, res)
                    except Exception:
                        continue
    _, order, sorder, res = best
    if res is None:  # fallback
        return ets(history, horizon)
    idx = utils.future_index(history, horizon)
    if return_model:
        return res, order, sorder, idx
    fc = res.forecast(horizon)
    return pd.Series(np.exp(np.asarray(fc)), index=idx)


def auto_arima_with_intervals(history: pd.Series, horizon: int, alpha: float = 0.2):
    """ARR forecast with (1-alpha) prediction intervals (back-transformed from log space)."""
    out = auto_arima(history, horizon, return_model=True)
    if isinstance(out, pd.Series):  # fell back to ETS (no intervals)
        pf = out
        return pf, pf * 0.96, pf * 1.04, ("ETS-fallback", None)
    res, order, sorder, idx = out
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pred = res.get_forecast(horizon)
        mean = np.exp(pred.predicted_mean.to_numpy())
        ci = pred.conf_int(alpha=alpha)
        lo = np.exp(ci.iloc[:, 0].to_numpy())
        hi = np.exp(ci.iloc[:, 1].to_numpy())
    return (pd.Series(mean, index=idx), pd.Series(lo, index=idx), pd.Series(hi, index=idx),
            (f"SARIMA{order}x{sorder}", res.aic))
