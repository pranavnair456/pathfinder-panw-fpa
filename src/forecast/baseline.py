"""
Baseline forecasters — the bar every "real" model must clear.

`seasonal_naive` repeats last year's monthly net-adds. On a trending growth series this
under-forecasts (it ignores acceleration), which is exactly why it's a baseline: if a fancy model
can't beat "next year looks like last year," the fancy model isn't earning its keep.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils


def seasonal_naive(history: pd.Series, horizon: int, season: int = utils.SEASON) -> pd.Series:
    """Forecast ARR level by repeating the last `season` months of net-adds."""
    adds = utils.to_netadds(history)
    last_season = adds.iloc[-season:].to_numpy()
    fc_adds = [last_season[i % season] for i in range(horizon)]
    idx = utils.future_index(history, horizon)
    return utils.integrate(history.iloc[-1], fc_adds, idx)


def naive_drift(history: pd.Series, horizon: int) -> pd.Series:
    """Random-walk-with-drift: extend the average recent monthly net-add. A second simple anchor."""
    adds = utils.to_netadds(history)
    drift = adds.iloc[-utils.SEASON:].mean()
    idx = utils.future_index(history, horizon)
    return utils.integrate(history.iloc[-1], np.repeat(drift, horizon), idx)


def seasonal_naive_drift(history: pd.Series, horizon: int, season: int = utils.SEASON) -> pd.Series:
    """Seasonal-naive PLUS a year-over-year drift on the net-adds.

    The fix for both naive failures: take last year's *seasonal shape* (which seasonal-naive has and
    drift lacks) and add the year-over-year growth in net-adds (which drift has and seasonal-naive
    lacks). On a series that is both trending and seasonal — like NGS ARR — capturing both is what
    earns a real, robust improvement over either baseline alone.
    """
    adds = utils.to_netadds(history)
    last_season = adds.iloc[-season:].to_numpy()
    yoy_trend = float(adds.iloc[-season:].mean() - adds.iloc[-2 * season:-season].mean())
    fc_adds = []
    for h in range(horizon):
        years_ahead = h // season + 1
        fc_adds.append(last_season[h % season] + yoy_trend * years_ahead)
    idx = utils.future_index(history, horizon)
    return utils.integrate(history.iloc[-1], fc_adds, idx)
