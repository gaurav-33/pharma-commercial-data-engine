-- ==============================================================================
-- PHARMA COMMERCIAL DATA ENGINE: PRODUCTION ANALYTICS SQL
-- ==============================================================================
-- Advanced business intelligence queries utilizing Common Table Expressions (CTEs)
-- and Window Functions for commercial performance analysis.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Category Market Share Percentage Over Time
-- Uses SUM() OVER(PARTITION BY ...) to compute category market penetration
-- ------------------------------------------------------------------------------
WITH monthly_category_sales AS (
    SELECT 
        anio,
        mes,
        codigo_atc,
        SUM(cantidad_vendida) AS category_volume
    FROM daily_sales
    GROUP BY anio, mes, codigo_atc
),
market_share_calculation AS (
    SELECT 
        anio,
        mes,
        codigo_atc,
        category_volume,
        -- Total commercial sales volume across all categories for that month
        SUM(category_volume) OVER(PARTITION BY anio, mes) AS total_monthly_market_volume
    FROM monthly_category_sales
)
SELECT 
    anio,
    mes,
    codigo_atc,
    ROUND(category_volume, 2) AS category_volume,
    ROUND(total_monthly_market_volume, 2) AS total_market_volume,
    -- Category market share %
    ROUND((category_volume * 100.0) / total_monthly_market_volume, 2) AS market_share_percentage
FROM market_share_calculation
ORDER BY anio, mes, category_volume DESC;


-- ------------------------------------------------------------------------------
-- QUERY 2: Month-over-Month (MoM) Volume Growth per ATC Category
-- Uses LAG() OVER(PARTITION BY ...) to compute historical velocity and growth
-- ------------------------------------------------------------------------------
WITH monthly_sales_aggregate AS (
    SELECT 
        anio,
        mes,
        codigo_atc,
        SUM(cantidad_vendida) AS total_sales
    FROM daily_sales
    GROUP BY anio, mes, codigo_atc
),
mom_lag_window AS (
    SELECT 
        anio,
        mes,
        codigo_atc,
        total_sales,
        -- Fetch volume from the immediately preceding month
        LAG(total_sales, 1) OVER (PARTITION BY codigo_atc ORDER BY anio, mes) AS prev_month_sales
    FROM monthly_sales_aggregate
)
SELECT 
    anio,
    mes,
    codigo_atc,
    ROUND(total_sales, 2) AS current_month_volume,
    ROUND(prev_month_sales, 2) AS previous_month_volume,
    ROUND(total_sales - prev_month_sales, 2) AS net_volume_change,
    CASE 
        WHEN prev_month_sales IS NULL THEN 0.0
        WHEN prev_month_sales = 0 THEN 0.0
        ELSE ROUND(((total_sales - prev_month_sales) * 100.0) / prev_month_sales, 2)
    END AS mom_growth_percentage
FROM mom_lag_window
ORDER BY codigo_atc, anio, mes;


-- ------------------------------------------------------------------------------
-- QUERY 3: 7-Day Rolling Moving Average of Commercial Sales Volume
-- Uses AVG() OVER (ORDER BY sale_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
-- ------------------------------------------------------------------------------
WITH daily_portfolio_volume AS (
    SELECT 
        fecha AS sale_date,
        SUM(cantidad_vendida) AS total_daily_volume
    FROM daily_sales
    GROUP BY fecha
)
SELECT 
    sale_date,
    ROUND(total_daily_volume, 2) AS daily_volume,
    -- 7-day rolling moving average
    ROUND(AVG(total_daily_volume) OVER (
        ORDER BY sale_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_7day_avg_volume
FROM daily_portfolio_volume
ORDER BY sale_date;


-- ------------------------------------------------------------------------------
-- QUERY 4: Category-Level 7-Day Rolling Moving Average
-- Windowing partitioned by drug category
-- ------------------------------------------------------------------------------
WITH daily_category_volume AS (
    SELECT 
        fecha AS sale_date,
        codigo_atc,
        SUM(cantidad_vendida) AS category_daily_volume
    FROM daily_sales
    GROUP BY fecha, codigo_atc
)
SELECT 
    sale_date,
    codigo_atc,
    ROUND(category_daily_volume, 2) AS daily_volume,
    ROUND(AVG(category_daily_volume) OVER (
        PARTITION BY codigo_atc 
        ORDER BY sale_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_7day_category_volume
FROM daily_category_volume
ORDER BY codigo_atc, sale_date;


-- ------------------------------------------------------------------------------
-- QUERY 5: Commercial Data Continuity & Ingestion Gap Audit
-- Identifies unrecorded calendar days in chronological sales data
-- ------------------------------------------------------------------------------
WITH chronological_sales_dates AS (
    SELECT DISTINCT 
        fecha AS sale_date,
        LEAD(fecha, 1) OVER (ORDER BY fecha) AS next_sale_date
    FROM daily_sales
),
calendar_gap_computation AS (
    SELECT 
        sale_date AS gap_starts_after,
        next_sale_date AS gap_resumes_on,
        CAST(ROUND(julianday(next_sale_date) - julianday(sale_date) - 1) AS INTEGER) AS missing_days_count
    FROM chronological_sales_dates
    WHERE next_sale_date IS NOT NULL
)
SELECT 
    gap_starts_after,
    gap_resumes_on,
    missing_days_count
FROM calendar_gap_computation
WHERE missing_days_count > 0
ORDER BY missing_days_count DESC;
