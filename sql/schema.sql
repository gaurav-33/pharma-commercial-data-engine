-- ==============================================================================
-- PHARMA COMMERCIAL DATA ENGINE: RELATIONAL SCHEMA DEFINITIONS
-- ==============================================================================
-- Schema for the daily commercial transaction staging & analytics warehouse.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS daily_sales (
    fecha TEXT NOT NULL,
    anio INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    hora INTEGER NOT NULL,
    dia_semana TEXT NOT NULL,
    codigo_atc TEXT NOT NULL,
    cantidad_vendida REAL NOT NULL
);
