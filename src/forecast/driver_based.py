"""
Driver-based (bottoms-up) forecaster — the model an FP&A team actually defends to a CFO.

Instead of extrapolating a line, it rebuilds ARR from its motions, exactly like the roll-forward:

    Ending = Beginning + New + Expansion + Platformization − Contraction − Churn

It reads the real organic motions from the warehouse up to the forecast cutoff (so it is
backtest-safe — no leakage), estimates each rate over the trailing 12 months, then projects them
forward with the fiscal-Q4 seasonality applied to new + expansion. The output is interpretable:
you can point at *why* the number moves.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import db

from . import utils

ORGANIC = ("Strata", "Prisma Cloud", "Cortex")


def _organic_components(cutoff: str) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(ORGANIC))
    return db.query(f"""
        SELECT month,
               SUM(beginning_arr) AS beg, SUM(new_arr) AS new_arr,
               SUM(expansion_arr) AS exp, SUM(platformization_arr) AS plat,
               SUM(contraction_arr) AS con, SUM(churn_arr) AS churn,
               SUM(ending_arr) AS ending
        FROM v_arr_rollforward
        WHERE platform IN ({placeholders}) AND month <= ?
        GROUP BY month ORDER BY month
    """, list(ORGANIC) + [cutoff])


def _seasonal_factor(dt: pd.Timestamp) -> float:
    return 1.25 if dt.month in (5, 6, 7) else (0.9 if dt.month in (8, 9, 10) else 1.0)


def forecast(history: pd.Series, horizon: int, return_components: bool = False,
             exp_mult: float = 1.0, churn_mult: float = 1.0, new_mult: float = 1.0,
             new_growth_add: float = 0.0):
    """Project organic ARR from trailing-12m motion rates. `history` sets the cutoff & start level.

    Scenario levers (used by trajectory.py for bull/bear): scale expansion / churn / new-business
    and shift the new-business growth rate. Defaults reproduce the base case.
    """
    cutoff = history.index[-1].strftime("%Y-%m")
    comp = _organic_components(cutoff)
    last12 = comp.tail(12)

    # rates as a fraction of beginning balance (retention motions)
    exp_rate = float((last12["exp"] / last12["beg"]).mean()) * exp_mult
    con_rate = float((last12["con"].abs() / last12["beg"]).mean())
    churn_rate = float((last12["churn"].abs() / last12["beg"]).mean()) * churn_mult
    plat_rate = float((last12["plat"] / last12["beg"]).mean())

    # new business: recent level + monthly growth (capped for sanity)
    new_recent = float(last12["new_arr"].tail(3).mean()) * new_mult
    new_12ago = float(comp["new_arr"].tail(15).head(3).mean()) if len(comp) >= 15 else new_recent
    new_growth = np.clip((new_recent / max(new_12ago, 1.0)) ** (1 / 12) - 1, -0.02, 0.06) \
        + new_growth_add

    idx = utils.future_index(history, horizon)
    base = float(history.iloc[-1])
    new_run = new_recent
    rows, levels = [], []
    for dt in idx:
        sf = _seasonal_factor(dt)
        new_run = new_run * (1 + new_growth)
        new = new_run * sf
        expansion = base * exp_rate * sf
        platformization = base * plat_rate
        contraction = base * con_rate
        churn = base * churn_rate
        net = new + expansion + platformization - contraction - churn
        base += net
        levels.append(base)
        rows.append({"month": dt, "new": new, "expansion": expansion,
                     "platformization": platformization, "contraction": -contraction,
                     "churn": -churn, "net": net, "ending": base})
    level = pd.Series(levels, index=idx)
    if return_components:
        return level, pd.DataFrame(rows).set_index("month"), {
            "exp_rate": exp_rate, "churn_rate": churn_rate, "con_rate": con_rate,
            "plat_rate": plat_rate, "new_growth": new_growth, "new_recent": new_recent}
    return level
