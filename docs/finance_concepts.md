# Finance Concepts — reference

A deeper reference for the FP&A, GAAP and M&A concepts used in Pathfinder. For the friendly
walkthrough, read [`../LEARN.md`](../LEARN.md).

## Recurring-revenue metrics
- **ARR / MRR** — annualized (monthly) run-rate of active recurring contracts. A point-in-time
  run-rate, *not* a GAAP revenue figure.
- **NGS ARR** — PANW's Next-Generation Security ARR: modern software subscriptions (cloud, SASE,
  AI-driven SecOps), excluding legacy hardware/perpetual. The strategic headline metric.
- **ARR roll-forward** — `Beginning + New + Expansion + Platformization + Inorganic − Contraction −
  Churn = Ending`. The fundamental FP&A bridge.
- **NRR (Net Revenue Retention)** — trailing cohort's current ARR ÷ prior-year ARR, incl. expansion
  and churn. >100% ⇒ self-growing base. **GRR** caps each account at prior ARR (no expansion credit).
- **Logo vs dollar retention** — counting customers vs counting ARR. Dollar retention can exceed
  100% even if some logos churn, if survivors expand more.
- **ARPU** — ARR ÷ active customers. Rising ARPU signals up-market mix / platformization.
- **Cohort analysis** — group customers by start period; track their ARR by age to see durability.

## GAAP / revenue recognition (ASC 606)
- **Ratable recognition** — subscription revenue is recognized evenly over the service period, not
  at booking. So ARR (run-rate today) ≠ revenue (recognized over time).
- **Deferred revenue** — a liability: cash billed/collected for undelivered service; converts to
  revenue as delivered. Current (<12m) vs non-current.
- **RPO (Remaining Performance Obligation)** — total contracted, not-yet-recognized revenue
  (backlog). Broader than deferred revenue (includes contracted-but-unbilled). **Current RPO**
  (cRPO) is the portion expected within 12 months.
- **Billings** ≈ revenue + Δ deferred revenue — a demand proxy.

## Profitability & efficiency
- **Gross margin** — (revenue − COGS) ÷ revenue. Software ≈ high; hardware drags it down.
- **Operating margin** — operating income ÷ revenue. Non-GAAP excludes SBC, amortization of
  intangibles, acquisition costs.
- **Adjusted free cash flow margin** — adj. FCF ÷ revenue; a cash-quality gauge. PANW targets 40%+
  by FY2028.
- **Rule of 40** — revenue growth % + (FCF or operating) margin % ≥ 40. Growth/profit trade-off.
- **SaaS magic number** — net-new (annualized) recurring revenue ÷ prior-period S&M; sales
  efficiency. >0.75 ≈ efficient.
- **CAC / LTV** — customer acquisition cost vs lifetime value. LTV ≈ annual ARPU × gross margin ×
  lifetime (≈ 1/annual gross churn, often capped). LTV/CAC > 3 ≈ efficient growth.

## Platformization
A go-to-market motion: drive customers to adopt **multiple** products on one platform. Economics:
higher switching costs (stickiness ⇒ higher GRR) and more cross-sell surface (⇒ higher NRR). PANW
incentivizes it and targets 4,000+ platformized customers by FY2030.

## M&A
- **Organic vs inorganic** — growth from the existing business vs from acquisitions.
- **Accretion / dilution** — whether a deal raises/lowers pro-forma EPS:
  `pro-forma EPS = (acquirer NI + target NI + after-tax synergies − after-tax financing cost) ÷
  (acquirer shares + new shares issued)`. Compare to standalone EPS.
- **Synergies** — **cost** (remove duplicate spend) + **revenue** (cross-sell). Phase in over time
  (S-curve), not at close.
- **Consideration mix** — cash (uses balance sheet / adds debt → interest cost) vs equity (issues
  shares → dilution). The mix drives the accretion math.
- **NPV / DCF** — discount incremental future cash flows to today; compare to price paid. A deal can
  be **EPS-dilutive yet NPV-positive** (and vice-versa) — judge on both.
- **ARR multiple** — deal value ÷ acquired ARR; a valuation yardstick (e.g., Chronosphere ≈ 21×).

## Forecasting terms
- **Seasonal-naive / drift** — naive baselines (repeat last season / extend average change).
- **ETS / SARIMA** — classical exponential-smoothing / autoregressive seasonal models.
- **Driver-based** — rebuild the metric from its operational motions; interpretable.
- **Rolling-origin CV / backtest** — repeated out-of-sample evaluation across historical cutoffs.
- **WAPE / MAPE / RMSE** — error metrics; WAPE = Σ|error| ÷ Σ|actual| (robust at large scale).
- **Ablation** — remove a feature group and measure the change in error (causal-ish attribution).
