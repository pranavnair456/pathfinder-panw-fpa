# LEARN.md — Pathfinder, explained in plain English

This is the teaching companion. If you're new to SaaS finance, read this top-to-bottom and you'll
understand every number in the app and *why* Palo Alto Networks (PANW) runs its business the way it
does. No jargon left unexplained. (All figures are synthetic but calibrated to PANW's real public
filings — see [`docs/assumptions.md`](docs/assumptions.md).)

---

## 1. The one-sentence story

PANW is shifting from selling boxes (firewalls) to selling **subscriptions** across three software
platforms, wants customers to buy *several* products at once ("platformization"), is buying its way
into new categories (CyberArk, Chronosphere), and has told Wall Street it will reach **$20B of
Next-Gen Security ARR by FY2030**. Pathfinder models whether and how that happens.

---

## 2. ARR and NGS ARR — the heartbeat metric

**ARR = Annual Recurring Revenue**: the annualized value of all active subscriptions *right now*.
If a customer signs a $1.2M/year contract, that's $1.2M of ARR the moment it's live — regardless of
how the accounting recognizes the revenue month by month. ARR is a *run-rate snapshot*, not an
accounting number.

**NGS ARR = Next-Generation Security ARR**: PANW's headline metric — ARR from its modern software
subscriptions (cloud, SASE, AI-driven security ops), *excluding* legacy hardware/perpetual licenses.
It's the number management is judged on because it captures the strategic transition. In this
project NGS ARR is **$8.78B** at the end of FY2026, up ~57% year over year.

> 💡 Why ARR and not revenue? Revenue (GAAP) for a subscription is recognized *ratably* — a 12-month
> deal books 1/12 of revenue each month. ARR tells you the forward run-rate *today*, which is more
> useful for steering the business. The two reconcile through deferred revenue and RPO (below).

---

## 3. The ARR roll-forward (the "bridge")

ARR moves every period through a small set of **motions**:

```
Beginning ARR
  + New            (brand-new customers / first product)
  + Expansion      (existing customers buying more)
  + Platformization(existing customers consolidating onto the platform)
  + Inorganic      (ARR that arrives via an acquisition)
  − Contraction    (existing customers buying less)
  − Churn          (customers who leave)
  = Ending ARR
```

This identity is the backbone of FP&A. In Pathfinder it **ties out to the penny for every single
platform-month** (see the Data Quality page) — that's not cosmetic; it's how you earn the right to
trust every downstream number. The "ARR bridge" waterfall chart shows exactly which motions drove a
quarter's change.

---

## 4. Retention: NRR and GRR (why this is the whole ballgame)

Take the group of customers who existed **12 months ago**. Look at what they're worth **today**:

- **Net Revenue Retention (NRR)** = today's ARR ÷ their ARR a year ago. Includes expansion *and*
  churn. **NRR > 100% means the existing customer base grows on its own**, before you win a single
  new logo. PANW runs ~120%; Pathfinder shows ~119%.
- **Gross Revenue Retention (GRR)** = same, but you *cap* each customer at last year's value (no
  credit for expansion). It's the pure "how much did we keep" floor. ~96% here.

**Why NRR is magical:** a business with 120% NRR is on an up-escalator. Even with zero new sales,
revenue grows 20% a year. That's the SaaS dream, and it's why retention beats acquisition.

### The platformization gap
Split NRR by whether a customer is "platformized":
- **Platformized customers: ~135% NRR** — they expand fast and rarely leave.
- **Single-product customers: ~114% NRR** — they barely hold.

That **gap is the entire economic case** for PANW's platformization strategy (Section 7).

---

## 5. RPO and deferred revenue (the "money already in the bag")

- **RPO (Remaining Performance Obligation)** = total contracted revenue PANW hasn't recognized yet —
  the backlog. PANW's RPO is **$18.4B**. It's a confidence signal: revenue already under contract.
- **Deferred revenue** = cash collected (or billed) for services not yet delivered; a *liability*
  until earned. As you deliver, it converts to revenue.
- **Billings** ≈ revenue + change in deferred revenue — a proxy for how much new business you
  invoiced this period.

> 💡 RPO is broader than deferred revenue: RPO includes contracted-but-not-yet-billed amounts too.

---

## 6. Rule of 40 and the SaaS magic number (efficiency gauges)

- **Rule of 40**: revenue growth % + profit margin % should exceed 40. It trades growth against
  profitability — you can pass by growing fast *or* by being very profitable. PANW does both;
  Pathfinder scores ~**69** (using adjusted FCF margin). Anything comfortably above 40 is elite.
- **SaaS magic number**: net-new ARR in a quarter ÷ prior-quarter sales & marketing spend. It asks
  "for every $1 of S&M, how much new ARR did we buy back?" Above ~0.75 means sales is paying off.

---

## 7. Platformization — what it is and why PANW pushes it so hard

"Platformization" = getting a customer to adopt **multiple** PANW products on one integrated
platform instead of buying point products from many vendors. PANW *incentivizes* this aggressively
(credits, discounts, free periods) and targets **4,000+ platformized customers by FY2030**.

Why pay customers to consolidate? Because of the retention gap in Section 4. A platformized customer
is **stickier** (ripping out an entire platform is hard) and **expands faster** (more products to
grow into). The Platformization ROI page models this as an investment: spend an incentive now, earn
a faster-compounding revenue stream later. Because the value is the *NRR gap compounded over years*,
the ROI is large — which is exactly why the strategy exists.

---

## 8. Organic vs inorganic growth (and why you must separate them)

- **Organic growth** = growth from the existing business — new customers, expansion.
- **Inorganic growth** = growth that arrives because you *bought* a company.

PANW's headline NGS ARR grew ~60% YoY — but ~$1.6B of that came from acquiring **CyberArk**
(identity security, ~$25B deal) and **Chronosphere** (observability, $3.35B). Strip those out and
**organic growth is ~25-30%**. Both numbers are real; mixing them up flatters the story. Good FP&A
always shows the split — the M&A page does exactly this.

---

## 9. M&A math: accretion/dilution and NPV

When a company buys another, two different questions matter:

1. **Accretion / dilution (short-term, EPS):** Does the deal raise or lower *earnings per share* next
   year? You add the target's earnings + synergies, subtract financing costs (interest on cash used,
   or the dilution from issuing new shares), and divide by the new share count. A fast-growing target
   that loses money is often **dilutive** in year 1.
2. **NPV (long-term, value):** Discount the future cash flows the deal creates back to today and
   compare to the price paid. A deal can be **NPV-positive** (creates value over time) even while
   being EPS-dilutive now.

Pathfinder's hypothetical tuck-in is the classic case: **−1.5% EPS year 1, but +$3.1B NPV**.
Sophisticated boards approve strategically sound, NPV-positive deals even when they pressure
near-term EPS. (Synergies = the extra value from combining: **cost synergies** = removing duplicate
costs; **revenue synergies** = cross-selling.)

---

## 10. Forecasting — why several methods, and when to trust each

Pathfinder forecasts **organic** NGS ARR (the smooth part — the M&A step-ups are contractual, not
forecastable). Models work on the **monthly net-add flow** (new ARR added each month), then add it
up into a level.

- **Seasonal-naive (baseline):** "next year's months look like last year's." Captures seasonality,
  ignores trend. The bar everything must beat.
- **Naive-drift:** extend the recent average net-add. Captures trend, ignores seasonality.
- **ETS / Holt-Winters:** exponential smoothing with trend (and optional seasonality).
- **SARIMA (auto-ARIMA):** classical time-series model chosen by a grid search.
- **XGBoost:** gradient-boosted trees on engineered features (lags, calendar, threat signals).
- **Driver-based:** rebuild ARR from its motions (new/expansion/churn rates) — *interpretable*.

**The honest finding:** on a big, smooth ARR base, **simple methods are very hard to beat** — a
well-known result in forecasting. So we *report that truthfully* and choose the **driver-based**
model for the strategic trajectory, not because it's the most accurate by a hair, but because it's
**interpretable and scenario-able** — you can flex assumptions a CFO will argue about. Knowing when
*not* to over-model is itself a sign of forecasting maturity.

**Backtesting** = pretend it's the past, forecast the "future," check against what actually
happened, repeated over many cutoffs (rolling-origin cross-validation). We score the **flow** (the
hard part), because the ARR *level* is so dominated by the existing base that everyone looks good.

---

## 11. The threat-signal idea (Option D)

PANW argues AI is "weaponizing" cyber-attacks, which should *pull forward* security demand. So:
could external threat data (CVE counts, breach disclosures, an "AI-threat index") **predict** demand
before it shows up in bookings?

We test it honestly with an **ablation**: the same model, with and without the threat features, on
identical backtest folds. Result: the signal **leads demand by ~2 months** and adding it improves
the near-term forecast by ~**17%** — enough to finally beat the naive baseline. But the lead is
short, so it helps the *next quarter*, not the multi-year $20B path (you can't observe future threat
activity). Reporting both the win **and** its limit is the whole point — that's intellectual honesty.

---

## 12. Putting it together: the $20B question

- Today: ~$8.8B NGS ARR (FY2026).
- Target: **$20B by FY2030** → implies sustaining a ~**23% CAGR** for four years.
- Pathfinder's base case (extrapolating today's *decelerating* growth) reaches only ~**$15B**.
- The bull case reaches ~**$18B**.

The takeaway: **$20B is an ambitious target that requires above-trend execution** — sustained new
business, the platformization flywheel, and continued M&A. Pathfinder lets you pull each of those
levers and see what it takes. That's what a real FP&A team would build to pressure-test a public
long-range target.

---

### Glossary quick-reference
ARR (run-rate recurring revenue) · NGS ARR (next-gen software ARR) · NRR/GRR (net/gross retention) ·
RPO (contracted backlog) · deferred revenue (billed-not-earned liability) · Rule of 40 (growth +
margin) · magic number (ARR per $ of S&M) · platformization (multi-product adoption) · organic vs
inorganic (built vs bought) · accretion/dilution (EPS impact of a deal) · NPV (discounted value
created) · synergies (cost savings + cross-sell) · backtest (historical out-of-sample test) ·
WAPE (weighted abs % error).
