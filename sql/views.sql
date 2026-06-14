-- ============================================================================
-- Pathfinder analytical views — FP&A logic in SQL (DuckDB)
-- ============================================================================
-- These views are the heart of the warehouse: ARR roll-forward, NGS ARR by platform with
-- organic/inorganic split, net/gross revenue retention, cohort retention, and the
-- RPO/deferred-revenue/billings roll. They feed the Python metrics layer and the app.
-- ============================================================================

-- A stable monthly sequence over the HISTORY window (for 12-month-offset retention math).
CREATE OR REPLACE VIEW v_month_seq AS
SELECT date_id, month, fiscal_year, fiscal_quarter, fy_label, fq_label,
       ROW_NUMBER() OVER (ORDER BY month) AS seq
FROM dim_date
WHERE is_history;

-- A stable quarter sequence (for cohort age in quarters).
CREATE OR REPLACE VIEW v_quarter_seq AS
SELECT fiscal_year, fiscal_quarter, ANY_VALUE(fq_label) AS fq_label,
       DENSE_RANK() OVER (ORDER BY fiscal_year, fiscal_quarter) AS qseq
FROM dim_date
WHERE is_history
GROUP BY fiscal_year, fiscal_quarter;

-- ---------------------------------------------------------------------------
-- 1) Event roll-up by month x platform, bucketed by motion
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_event_monthly AS
SELECT
    month,
    platform,
    SUM(CASE WHEN event_type = 'new'                  THEN arr_delta ELSE 0 END) AS new_arr,
    SUM(CASE WHEN event_type = 'expansion'            THEN arr_delta ELSE 0 END) AS expansion_arr,
    SUM(CASE WHEN event_type = 'platformization'      THEN arr_delta ELSE 0 END) AS platformization_arr,
    SUM(CASE WHEN event_type = 'inorganic_onboarding' THEN arr_delta ELSE 0 END) AS inorganic_arr,
    SUM(CASE WHEN event_type = 'contraction'          THEN arr_delta ELSE 0 END) AS contraction_arr,
    SUM(CASE WHEN event_type = 'churn'                THEN arr_delta ELSE 0 END) AS churn_arr,
    SUM(arr_delta)                                                               AS net_arr
FROM fact_subscription_events
GROUP BY month, platform;

-- ---------------------------------------------------------------------------
-- 2) ARR ROLL-FORWARD by platform:  Beginning + motions = Ending
--    (the canonical FP&A bridge; window SUM gives the running ending balance)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_arr_rollforward AS
WITH running AS (
    SELECT em.*,
           SUM(net_arr) OVER (PARTITION BY platform ORDER BY month) AS ending_arr
    FROM v_event_monthly em
)
SELECT
    month,
    platform,
    LAG(ending_arr, 1, 0) OVER (PARTITION BY platform ORDER BY month) AS beginning_arr,
    new_arr,
    expansion_arr,
    platformization_arr,
    inorganic_arr,
    contraction_arr,
    churn_arr,
    net_arr,
    ending_arr
FROM running;

-- ---------------------------------------------------------------------------
-- 3) NGS ARR by platform, with organic/inorganic flag
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ngs_arr_by_platform AS
SELECT r.month, r.platform, p.segment_group, p.source, p.is_organic, r.ending_arr
FROM v_arr_rollforward r
JOIN (SELECT DISTINCT platform, segment_group, source, is_organic FROM dim_platform) p
  USING (platform);

-- 3b) NGS ARR total with organic vs inorganic split (powers the M&A decomposition)
CREATE OR REPLACE VIEW v_ngs_arr_summary AS
SELECT
    month,
    SUM(ending_arr)                                            AS total_ngs_arr,
    SUM(CASE WHEN is_organic THEN ending_arr ELSE 0 END)       AS organic_ngs_arr,
    SUM(CASE WHEN NOT is_organic THEN ending_arr ELSE 0 END)   AS inorganic_ngs_arr
FROM v_ngs_arr_by_platform
GROUP BY month;

-- ---------------------------------------------------------------------------
-- 4) Customer monthly ARR (materialized by ETL into table `customer_arr_monthly`)
--    Dense customer x month grid from the customer's cohort onward; running ARR.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_customer_arr_monthly AS
WITH cust_month AS (
    SELECT c.customer_id, s.date_id AS month, s.seq
    FROM dim_customer c
    JOIN v_month_seq s ON s.date_id >= c.acquisition_cohort_month
),
deltas AS (
    SELECT customer_id, month, SUM(arr_delta) AS delta
    FROM fact_subscription_events
    GROUP BY customer_id, month
)
SELECT
    cm.customer_id,
    cm.month,
    cm.seq,
    GREATEST(SUM(COALESCE(d.delta, 0))
             OVER (PARTITION BY cm.customer_id ORDER BY cm.seq), 0) AS arr
FROM cust_month cm
LEFT JOIN deltas d ON d.customer_id = cm.customer_id AND d.month = cm.month;

-- Materialize the heavy grid as a table (the retention/cohort views below read it directly
-- for app responsiveness). Built here so downstream views resolve in dependency order.
CREATE OR REPLACE TABLE customer_arr_monthly AS SELECT * FROM v_customer_arr_monthly;
CREATE INDEX IF NOT EXISTS idx_cam_cust ON customer_arr_monthly(customer_id);
CREATE INDEX IF NOT EXISTS idx_cam_seq  ON customer_arr_monthly(seq);

-- ---------------------------------------------------------------------------
-- 5) Net & Gross Revenue Retention + logo retention (trailing 12 months)
--    NRR = current ARR of the cohort that existed 12m ago / their ARR 12m ago
--    GRR = same but each account capped at its prior ARR (no expansion credit)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_nrr_grr AS
WITH base AS (
    SELECT a.month, a.customer_id, a.arr AS arr_now, b.arr AS arr_prior
    FROM customer_arr_monthly a
    JOIN customer_arr_monthly b
      ON a.customer_id = b.customer_id AND a.seq = b.seq + 12
    WHERE b.arr > 0
)
SELECT
    month,
    SUM(arr_now)                  / NULLIF(SUM(arr_prior), 0) AS nrr,
    SUM(LEAST(arr_now, arr_prior))/ NULLIF(SUM(arr_prior), 0) AS grr,
    COUNT(*) FILTER (WHERE arr_now > 0) * 1.0 / COUNT(*)      AS logo_retention,
    COUNT(*)                                                  AS cohort_logos
FROM base
GROUP BY month;

-- 5b) NRR split: platformized vs non-platformized (the platformization value proof)
CREATE OR REPLACE VIEW v_nrr_by_platformization AS
WITH base AS (
    SELECT a.month, a.customer_id, a.arr AS arr_now, b.arr AS arr_prior,
           c.platformized_flag
    FROM customer_arr_monthly a
    JOIN customer_arr_monthly b
      ON a.customer_id = b.customer_id AND a.seq = b.seq + 12
    JOIN dim_customer c ON c.customer_id = a.customer_id
    WHERE b.arr > 0
)
SELECT
    month,
    platformized_flag,
    SUM(arr_now) / NULLIF(SUM(arr_prior), 0)                  AS nrr,
    SUM(LEAST(arr_now, arr_prior)) / NULLIF(SUM(arr_prior),0) AS grr,
    COUNT(*)                                                  AS cohort_logos
FROM base
GROUP BY month, platformized_flag;

-- ---------------------------------------------------------------------------
-- 6) Cohort retention matrix (by cohort fiscal quarter x age in quarters)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_customer_quarter_arr AS
SELECT customer_id, fiscal_year, fiscal_quarter, fq_label, qseq, arr
FROM (
    SELECT cam.customer_id, d.fiscal_year, d.fiscal_quarter, d.fq_label,
           qs.qseq, cam.arr,
           ROW_NUMBER() OVER (PARTITION BY cam.customer_id, d.fiscal_year, d.fiscal_quarter
                              ORDER BY cam.month DESC) AS rn
    FROM customer_arr_monthly cam
    JOIN dim_date d ON d.date_id = cam.month
    JOIN v_quarter_seq qs ON qs.fiscal_year = d.fiscal_year
                          AND qs.fiscal_quarter = d.fiscal_quarter
    WHERE d.is_quarter_end_month
) WHERE rn = 1;

CREATE OR REPLACE VIEW v_cohort_retention AS
WITH firstq AS (
    SELECT customer_id, MIN(qseq) AS cohort_qseq
    FROM v_customer_quarter_arr WHERE arr > 0 GROUP BY customer_id
),
base AS (
    SELECT cq.customer_id, f.cohort_qseq, cq.qseq - f.cohort_qseq AS age_q, cq.arr,
           FIRST_VALUE(cq.arr) OVER (PARTITION BY cq.customer_id ORDER BY cq.qseq) AS init_arr
    FROM v_customer_quarter_arr cq
    JOIN firstq f ON f.customer_id = cq.customer_id
    WHERE cq.qseq >= f.cohort_qseq
)
SELECT
    b.cohort_qseq,
    qs.fq_label                                       AS cohort_label,
    b.age_q,
    COUNT(DISTINCT b.customer_id)                     AS cohort_logos,
    SUM(b.arr)                                        AS arr,
    SUM(b.arr) / NULLIF(SUM(b.init_arr), 0)           AS dollar_retention
FROM base b
JOIN v_quarter_seq qs ON qs.qseq = b.cohort_qseq
GROUP BY b.cohort_qseq, qs.fq_label, b.age_q
ORDER BY b.cohort_qseq, b.age_q;

-- ---------------------------------------------------------------------------
-- 7) RPO / deferred revenue / implied billings roll
--    Implied billings (approx) = recognized revenue + change in total deferred revenue
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_rpo_deferred AS
WITH f AS (
    SELECT month, fiscal_year, fiscal_quarter, total_revenue, rpo,
           deferred_revenue_current, deferred_revenue_noncurrent,
           deferred_revenue_current + deferred_revenue_noncurrent AS total_deferred
    FROM fact_financials
)
SELECT
    month, fiscal_year, fiscal_quarter, total_revenue, rpo,
    deferred_revenue_current, deferred_revenue_noncurrent, total_deferred,
    total_revenue
      + (total_deferred - LAG(total_deferred) OVER (ORDER BY month)) AS implied_billings
FROM f;

-- ---------------------------------------------------------------------------
-- 8) Plan vs actual (long form) for variance analysis
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_actual_vs_plan AS
SELECT
    f.month, f.fiscal_year, f.fiscal_quarter,
    f.ngs_arr_total                                    AS actual_ngs_arr,
    p_ngs.plan_value                                   AS plan_ngs_arr,
    f.total_revenue                                    AS actual_revenue,
    p_rev.plan_value                                   AS plan_revenue,
    f.operating_margin                                 AS actual_op_margin,
    p_om.plan_value                                    AS plan_op_margin
FROM fact_financials f
LEFT JOIN fact_plan p_ngs ON p_ngs.month = f.month AND p_ngs.metric = 'ngs_arr_total'
       AND p_ngs.plan_version = 'Board-Approved Plan'
LEFT JOIN fact_plan p_rev ON p_rev.month = f.month AND p_rev.metric = 'total_revenue'
       AND p_rev.plan_version = 'Board-Approved Plan'
LEFT JOIN fact_plan p_om  ON p_om.month  = f.month AND p_om.metric  = 'operating_margin'
       AND p_om.plan_version = 'Board-Approved Plan';
