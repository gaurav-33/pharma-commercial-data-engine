-- ==============================================================================
-- PHARMA COMMERCIAL DATA ENGINE: ANALYTICAL PERFORMANCE INDEXES
-- ==============================================================================
-- Optimized indexes supporting time series partitioning, windowing, and aggregations.
-- ==============================================================================

CREATE INDEX IF NOT EXISTS idx_daily_sales_fecha 
    ON daily_sales (fecha);

CREATE INDEX IF NOT EXISTS idx_daily_sales_atc 
    ON daily_sales (codigo_atc);

CREATE INDEX IF NOT EXISTS idx_daily_sales_period 
    ON daily_sales (anio, mes);

CREATE INDEX IF NOT EXISTS idx_daily_sales_atc_fecha 
    ON daily_sales (codigo_atc, fecha);
