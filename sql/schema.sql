-- ============================================================================
-- Pathfinder star schema (DuckDB) — reference DDL
-- ============================================================================
-- This documents the canonical table contracts. In practice src/etl.py loads the
-- committed CSVs with read_csv_auto (which infers these types) so the warehouse can be
-- rebuilt in one step. Grain & keys:
--
--   FACTS                              GRAIN                         FK -> DIM
--   fact_subscription_events          one ARR-changing event        customer_id->dim_customer
--                                                                    platform->dim_platform
--   fact_financials                   one month (GL roll-up)        month->dim_date.date_id
--   fact_plan                         month x metric x plan_version  month->dim_date.date_id
--   fact_ma_deals                     one M&A deal                   platform->dim_platform
--   fact_threat_signals               one month                     month->dim_date.date_id
--
--   DIMENSIONS
--   dim_date (date_id = 'YYYY-MM')    one month (Aug2020-Jul2030, incl. forecast horizon)
--   dim_platform                      one platform x module
--   dim_customer                      one customer
-- ============================================================================

CREATE TABLE IF NOT EXISTS dim_date (
    date_id            VARCHAR PRIMARY KEY,   -- 'YYYY-MM'
    month              DATE,
    fiscal_year        INTEGER,               -- PANW FY ends Jul 31
    fiscal_quarter     INTEGER,               -- 1..4 (FQ1=Aug-Oct ... FQ4=May-Jul)
    fy_label           VARCHAR,
    fq_label           VARCHAR,
    calendar_year      INTEGER,
    calendar_month     INTEGER,
    is_quarter_end_month BOOLEAN,
    is_history         BOOLEAN                 -- TRUE for actuals (<= Jul 2026)
);

CREATE TABLE IF NOT EXISTS dim_platform (
    platform_id        INTEGER PRIMARY KEY,
    platform           VARCHAR,               -- Strata / Prisma Cloud / Cortex / Identity / Observability
    segment_group      VARCHAR,
    module             VARCHAR,
    source             VARCHAR,               -- organic / CyberArk / Chronosphere
    is_organic         BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id              INTEGER PRIMARY KEY,
    customer_name            VARCHAR,
    segment                  VARCHAR,          -- SMB / Commercial / Enterprise / Strategic-Global
    region                   VARCHAR,
    industry                 VARCHAR,
    acquisition_cohort_month VARCHAR,          -- 'YYYY-MM'
    platformized_flag        BOOLEAN,
    platformization_date     VARCHAR,
    source                   VARCHAR,          -- organic / CyberArk / Chronosphere
    organic_inorganic        VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_subscription_events (
    event_id      BIGINT PRIMARY KEY,
    month         VARCHAR,                     -- 'YYYY-MM'  -> dim_date.date_id
    customer_id   INTEGER,                     -- -> dim_customer
    platform      VARCHAR,                     -- -> dim_platform.platform
    module        VARCHAR,
    event_type    VARCHAR,                     -- new/expansion/contraction/renewal/churn/platformization/inorganic_onboarding
    arr_delta     DOUBLE,                      -- signed ARR change ($)
    acv           DOUBLE,
    term_months   INTEGER
);

CREATE TABLE IF NOT EXISTS fact_financials (
    month                       VARCHAR,        -- -> dim_date.date_id
    fiscal_year                 VARCHAR,
    fiscal_quarter              VARCHAR,
    total_revenue               DOUBLE,
    product_revenue             DOUBLE,
    subscription_revenue        DOUBLE,
    cogs                        DOUBLE,
    gross_profit                DOUBLE,
    sales_marketing             DOUBLE,
    research_development        DOUBLE,
    general_admin               DOUBLE,
    operating_income            DOUBLE,
    operating_margin            DOUBLE,
    ngs_arr_total               DOUBLE,
    rpo                         DOUBLE,
    deferred_revenue_current    DOUBLE,
    deferred_revenue_noncurrent DOUBLE,
    adjusted_free_cash_flow     DOUBLE,
    fcf_margin                  DOUBLE
);

CREATE TABLE IF NOT EXISTS fact_plan (
    month        VARCHAR,
    metric       VARCHAR,
    plan_value   DOUBLE,
    plan_version VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_ma_deals (
    deal_name              VARCHAR,
    platform               VARCHAR,
    deal_value_usd         DOUBLE,
    cash_pct               DOUBLE,
    equity_pct             DOUBLE,
    target_arr_usd         DOUBLE,
    target_arr_growth      DOUBLE,
    close_date             VARCHAR,
    integration_ramp_months INTEGER,
    cost_synergy_pct       DOUBLE,
    revenue_synergy_pct    DOUBLE,
    is_hypothetical        BOOLEAN
);

CREATE TABLE IF NOT EXISTS fact_threat_signals (
    month                  VARCHAR,
    cve_count              INTEGER,
    disclosed_breach_count INTEGER,
    ai_threat_index        DOUBLE
);
