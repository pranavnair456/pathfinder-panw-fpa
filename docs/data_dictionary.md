# Data Dictionary (auto-generated)

_Generated from the live DuckDB warehouse by `src/governance.generate_data_dictionary()`._


> All data is synthetic — see [assumptions.md](assumptions.md).


**Lineage:** `data/generate.py` → `data/raw/*.csv` → `src/etl.py` → `data/warehouse.duckdb` (tables) → `sql/views.sql` (views) → `src/*` (metrics & models) → `streamlit_app.py` (app). Governance (`src/governance.py`) validates the raw CSVs and reconciles the warehouse.


## `dim_date`  (120 rows)

| column | type |
|---|---|
| month | DATE |
| fiscal_year | BIGINT |
| fiscal_quarter | BIGINT |
| fy_label | VARCHAR |
| fq_label | VARCHAR |
| calendar_year | BIGINT |
| calendar_month | BIGINT |
| is_quarter_end_month | BOOLEAN |
| is_history | BOOLEAN |
| date_id | VARCHAR |


## `dim_platform`  (17 rows)

| column | type |
|---|---|
| platform_id | BIGINT |
| platform | VARCHAR |
| segment_group | VARCHAR |
| module | VARCHAR |
| source | VARCHAR |
| is_organic | BOOLEAN |


## `dim_customer`  (8,236 rows)

| column | type |
|---|---|
| customer_id | BIGINT |
| customer_name | VARCHAR |
| segment | VARCHAR |
| region | VARCHAR |
| industry | VARCHAR |
| acquisition_cohort_month | VARCHAR |
| platformized_flag | BOOLEAN |
| platformization_date | VARCHAR |
| source | VARCHAR |
| organic_inorganic | VARCHAR |


## `fact_subscription_events`  (70,167 rows)

| column | type |
|---|---|
| event_id | BIGINT |
| month | VARCHAR |
| customer_id | BIGINT |
| platform | VARCHAR |
| module | VARCHAR |
| event_type | VARCHAR |
| arr_delta | DOUBLE |
| acv | DOUBLE |
| term_months | BIGINT |


## `fact_financials`  (72 rows)

| column | type |
|---|---|
| month | VARCHAR |
| fiscal_year | VARCHAR |
| fiscal_quarter | VARCHAR |
| total_revenue | DOUBLE |
| product_revenue | DOUBLE |
| subscription_revenue | DOUBLE |
| cogs | DOUBLE |
| gross_profit | DOUBLE |
| sales_marketing | DOUBLE |
| research_development | DOUBLE |
| general_admin | DOUBLE |
| operating_income | DOUBLE |
| operating_margin | DOUBLE |
| ngs_arr_total | DOUBLE |
| rpo | DOUBLE |
| deferred_revenue_current | DOUBLE |
| deferred_revenue_noncurrent | DOUBLE |
| adjusted_free_cash_flow | DOUBLE |
| fcf_margin | DOUBLE |


## `fact_plan`  (312 rows)

| column | type |
|---|---|
| month | VARCHAR |
| metric | VARCHAR |
| plan_value | DOUBLE |
| plan_version | VARCHAR |


## `fact_ma_deals`  (3 rows)

| column | type |
|---|---|
| deal_name | VARCHAR |
| platform | VARCHAR |
| deal_value_usd | BIGINT |
| cash_pct | DOUBLE |
| equity_pct | DOUBLE |
| target_arr_usd | BIGINT |
| target_arr_growth | DOUBLE |
| close_date | DATE |
| integration_ramp_months | BIGINT |
| cost_synergy_pct | DOUBLE |
| revenue_synergy_pct | DOUBLE |
| is_hypothetical | BOOLEAN |


## `fact_threat_signals`  (72 rows)

| column | type |
|---|---|
| month | VARCHAR |
| cve_count | BIGINT |
| disclosed_breach_count | BIGINT |
| ai_threat_index | DOUBLE |


## `customer_arr_monthly`  (286,846 rows)

| column | type |
|---|---|
| customer_id | BIGINT |
| month | VARCHAR |
| seq | BIGINT |
| arr | DOUBLE |


## Analytical views (see `sql/views.sql`)

- `v_actual_vs_plan`
- `v_arr_rollforward`
- `v_cohort_retention`
- `v_customer_arr_monthly`
- `v_customer_quarter_arr`
- `v_event_monthly`
- `v_month_seq`
- `v_ngs_arr_by_platform`
- `v_ngs_arr_summary`
- `v_nrr_by_platformization`
- `v_nrr_grr`
- `v_quarter_seq`
- `v_rpo_deferred`
