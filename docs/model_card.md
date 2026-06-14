# Model Card — NGS ARR Forecasting

## Objective
Forecast **organic** NGS ARR (monthly) to support the FY2030 $20B trajectory and near-term planning.
Inorganic (M&A) ARR is handled separately (it's a contractual step-up, not a forecastable signal).

## Data
Synthetic, seeded, calibrated to PANW public filings. Target series: organic NGS ARR, FY2021–FY2026
monthly (72 points). Models operate on the monthly net-add **flow**, integrated back to a level.

## Models evaluated
| Model | Family | Notes |
|---|---|---|
| Seasonal-Naive | baseline | repeat last year's monthly net-adds (the bar) |
| Naive-Drift | baseline | extend trailing-12m average net-add |
| Seasonal-Naive + Drift | baseline+ | last year's shape + YoY growth |
| ETS (Holt-Winters) | classical | damped trend + multiplicative seasonal (robust fallback) |
| Auto-ARIMA | classical | statsmodels SARIMAX grid, AIC-selected |
| XGBoost | ML | lags + calendar features (recursive multi-step) |
| XGBoost + Threat | ML | + lagged, leakage-safe threat features (Option D) |
| Driver-Based | structural | bottoms-up roll-forward projection (scenario levers) |

## Backtest (rolling-origin CV, 9 folds, 6-month horizon, scored on flow WAPE)
| Model | Flow WAPE | Skill vs baseline |
|---|---|---|
| **Naive-Drift** | **0.389** | **+7.6%** |
| Seasonal-Naive (baseline) | 0.421 | 0.0% |
| Seasonal-Naive + Drift | 0.460 | −9.3% |
| Auto-ARIMA | 0.536 | −27.2% |
| XGBoost | 0.544 | −29.1% |
| Driver-Based | 0.572 | −35.7% |
| ETS (Holt-Winters) | 0.697 | −65.4% |
| XGBoost + Threat | 0.736 | −74.8% |

_(Live/exact values: `data/backtest_results.json` and the Forecast page.)_

## Honest interpretation
- **Level error is uninformative**: the ARR base dwarfs monthly motion, so every model scores ~1–3%
  level WAPE. The discriminating test is the **flow** (net-new ARR), reported above.
- On this smooth, decelerating aggregate, **simple methods win** — naive-drift beats the
  seasonal-naive baseline by ~8%; the classical/ML models do *not* beat the baseline at the 6-month
  multi-step horizon. This is a well-documented forecasting phenomenon (simple methods are strong at
  aggregate levels), and we report it rather than over-fitting to manufacture a "win."
- **XGBoost + Threat looks poor here** because at a 6-month *multi-step* horizon the ~2-month threat
  lead is unobservable for most of the window. Its value shows up in the **1-step ablation**, where
  it gives a **+17.3% lift and beats the seasonal-naive baseline** (see Threat-Signal page /
  `data/threat_ablation.json`). Threat helps the near term; it cannot help the multi-year path.

## Chosen production model
**Driver-Based.** Rationale: for *strategic planning* (the $20B trajectory), interpretability and
the ability to flex explicit assumptions (new-business growth, expansion, churn, platformization)
outweigh a few points of backtest accuracy. The naive methods win on raw accuracy but can't answer
"what if we lift platformization?" — the questions a CFO actually asks. For **near-term demand**
nowcasting, the **XGBoost + Threat** 1-step model is preferred (it beats the baseline).

## Limitations
- Synthetic data: conclusions are about *method behaviour*, not literal PANW outcomes.
- Short series (72 months) limits ML; recursive multi-step compounds error.
- Driver-based extrapolation assumes recent motion rates persist (scenario levers bound this).
- Threat lift is real but bounded to the lead window; do not extrapolate it to long horizons.

## Library choices
statsmodels (ETS/SARIMAX) + a custom auto-ARIMA grid and XGBoost. **pmdarima and prophet were
intentionally omitted** — fragile to build on Python 3.12 / NumPy 2 and heavy for Streamlit Cloud;
statsmodels + a transparent grid is more robust and shows the selection logic explicitly.
