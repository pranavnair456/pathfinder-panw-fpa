# Engineer Doc — Schema & Pipeline, with a proposed change

**Re:** Same Q3 FY2026 finding as the [CFO memo](cfo_memo.md) — "headline +60% NGS ARR but organic
+28%, ~$1.6B inorganic." This note covers how that number is produced today and a schema change to
make organic/inorganic attribution first-class.

## Pipeline (lineage)
```
data/generate.py ─▶ data/raw/*.csv ─▶ src/etl.py ─▶ data/warehouse.duckdb (tables)
                 ─▶ sql/views.sql (views) ─▶ src/* (metrics/forecast/ma) ─▶ streamlit_app.py
src/governance.py validates raw CSVs and reconciles the warehouse.
```

## Relevant schema (star)
- `fact_subscription_events` (grain: one ARR-changing event) — `event_id`, `month`, `customer_id`,
  `platform`, `module`, `event_type` (new/expansion/contraction/renewal/churn/platformization/
  inorganic_onboarding), `arr_delta`, `acv`, `term_months`.
- `dim_customer` — `customer_id`, …, `organic_inorganic`, `source` (organic / CyberArk / Chronosphere).
- `dim_platform` — `platform`, `is_organic`, `source`.
- `fact_ma_deals` — `deal_name`, `platform`, `deal_value_usd`, `target_arr_usd`, `close_date`, …

## How "organic vs inorganic" is computed today
`v_ngs_arr_summary` sums ending ARR and splits on `dim_platform.is_organic` (Identity/Observability =
inorganic). This works because each acquired book maps to a dedicated platform — but it's
**inference by platform**, not an explicit deal link. Limitations:
- Can't attribute a *specific* event to a *specific* deal (CyberArk vs a future identity tuck-in both
  land on `Identity`).
- Post-close **cross-sell of an organic product into an acquired customer** is counted organic by
  platform, which is correct, but we can't easily produce a "deal contribution incl. cross-sell" view.

## Proposed change: add an explicit deal dimension + FK
Add a nullable `deal_id` to `fact_subscription_events` and a `dim_deal` (promote `fact_ma_deals`):

```sql
ALTER TABLE fact_subscription_events ADD COLUMN deal_id INTEGER;   -- NULL = organic
-- dim_deal(deal_id PK, deal_name, platform, close_date, ...)  (from fact_ma_deals)
-- backfill: events with event_type='inorganic_onboarding' OR customer.source<>'organic'
--           -> deal_id of the matching deal; all others stay NULL (organic).
```

Then organic/inorganic (and *per-deal* contribution) become explicit at any grain:

```sql
SELECT d.fiscal_year, d.fiscal_quarter,
       SUM(CASE WHEN e.deal_id IS NULL THEN e.arr_delta ELSE 0 END) AS organic_net_adds,
       SUM(CASE WHEN e.deal_id IS NOT NULL THEN e.arr_delta ELSE 0 END) AS inorganic_net_adds
FROM fact_subscription_events e JOIN dim_date d ON d.date_id = e.month
GROUP BY 1,2;
```

### Why
- **Correctness/auditability:** organic/inorganic stops being a platform-name heuristic and becomes a
  real, backfillable foreign key — survives future deals that share a platform.
- **New capability:** per-deal ARR contribution and integration tracking (ties directly to
  `src/ma.integration_ramp`) without bespoke logic.
- **Low blast radius:** column is nullable and additive; existing `is_organic` views keep working.

### Impact / rollout
1. Add `dim_deal`, add nullable `deal_id`, backfill in `etl.py` (one-time mapping).
2. Add `pandera` check: `event_type='inorganic_onboarding' ⇒ deal_id IS NOT NULL`.
3. Add `v_ngs_arr_by_deal`; migrate `v_ngs_arr_summary` to derive the split from `deal_id`
   (fallback to `is_organic` during transition).
4. Reconciliation invariant unchanged: roll-forward must still tie to the penny.

**Estimate:** ~½ day (schema + backfill + one view + tests). No change to the generator's calibration.
