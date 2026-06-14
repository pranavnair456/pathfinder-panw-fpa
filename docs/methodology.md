# Methodology

How Pathfinder is built and why each modelling choice was made. All data is synthetic and
calibrated to PANW public filings (see [`assumptions.md`](assumptions.md)).

## Data & warehouse
- **Synthetic, seeded generator** (`data/generate.py`, seed 42) produces a customer-level
  subscription-event ledger plus GL financials, plan, M&A and threat tables.
- **Reconcile-by-construction:** the ledger is the source of truth for ARR. For each platform-month
  we know the target ending ARR (from a curve calibrated to disclosed NGS ARR), emit realistic
  motions (new / expansion / contraction / churn / platformization), then add one small balancing
  event so ending ARR equals target **exactly**. This makes the ARR roll-forward tie to the penny
  and gives the governance layer a real reconciliation to verify.
- **Realistic lumpiness:** within-quarter monthly paths are drawn from a Dirichlet around a
  back-loaded shape, so the flow is realistically noisy *while quarter-end anchors stay exact*. This
  is what makes model comparison meaningful (a perfectly smooth series is trivially forecastable).
- **Star schema in DuckDB** (`src/etl.py`, `sql/`): typed dimension/fact tables + analytical views
  (ARR roll-forward, NRR/GRR, cohorts, RPO roll) expressed in SQL with window functions.

## Calibration to reality
- The GAAP backbone (revenue, RPO, deferred revenue) is anchored to PANW's **SEC XBRL** series.
- NGS ARR is calibrated to disclosed quarter-end values; recent quarters are verified, FY21–FY23 are
  a documented back-cast. Per-platform splits and old product/subscription splits are **[MODELED]**
  (PANW doesn't disclose them) and clearly labelled.

## Metrics
ARR roll-forward, NGS ARR by platform with organic/inorganic split, NRR/GRR (overall and by
platformization), ARPU, CAC, LTV (lifetime capped at 10y), Rule of 40, SaaS magic number. Unit
economics are illustrative and assumption-driven; assumptions live in `src/metrics.py`.

## Forecasting (Option A)
- **Target = organic NGS ARR.** Inorganic ARR is a contractual M&A step-up, not forecastable; it's
  added back in `trajectory.py` and modelled explicitly in `src/ma.py`.
- Models forecast the **net-add flow** then integrate to a level.
- Models: seasonal-naive, naive-drift, seasonal-naive+drift, ETS (damped trend, multiplicative
  seasonal with a robust fallback), auto-ARIMA (statsmodels grid by AIC), XGBoost (lags + calendar +
  optional lagged threat features), driver-based (bottoms-up roll-forward with scenario levers).
- **Evaluation:** rolling-origin cross-validation, scoring both the level and the flow. We select on
  **flow WAPE** because the ARR level is dominated by the existing base (level error is ~uniformly
  tiny, hence uninformative).
- **Honest finding:** on a smooth ARR aggregate, simple methods are strong and hard to beat — a
  classic forecasting result. See [`model_card.md`](model_card.md).
- **Chosen production model: driver-based**, for the strategic $20B trajectory — slightly behind the
  best naive method on pure accuracy, but interpretable and scenario-able (the right tool for
  planning, where you must defend assumptions, not just minimize error).

## Trajectory & scenarios
`trajectory.py` projects organic ARR with the driver model under base/bull/bear assumption levers,
adds a decaying inorganic ramp, and measures the path to $20B by FY2030. A solver inverts the
question: how many platformizations would close the gap.

## Platformization ROI (Option B)
Investment framing: incentive spend now → incremental gross profit later, where incremental ARR =
starting ARR × (NRR_platformized^t − NRR_counterfactual^t). NPV/IRR/payback + a one-at-a-time
tornado. Value is dominated by the NRR gap (the honest core of the thesis).

## M&A (Option C)
Organic/inorganic decomposition; S-curve integration ramp with cost + revenue synergy realization;
banker-style accretion/dilution (financing + target NI + after-tax synergies → pro-forma EPS) and a
DCF NPV for a hypothetical tuck-in. Acquirer baselines are illustrative, anchored to PANW scale.

## Threat signals (Option D)
Lagged cross-correlation + a 1-step ablation (XGBoost with vs without lagged threat features). The
signal is constructed to lead the *net-add shock* by ~2 months with deliberate noise, so the lift is
real but bounded. See [`model_card.md`](model_card.md).

## Governance
pandera schemas, referential integrity, and reconciliation (ARR roll-forward identity; sub-ledger ↔
GL NGS ARR tie within 1%). Surfaced on the Data Quality page; lineage in `data_dictionary.md`.

## Reproducibility
Seeded RNG; pinned `requirements.txt` (Python 3.12); committed CSVs + `warehouse.duckdb` + cached
backtest/ablation/narrative JSON, so the deployed app runs with no build step and no secrets.
