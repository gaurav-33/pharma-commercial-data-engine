# pharma-commercial-data-engine 💊

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Architecture](https://img.shields.io/badge/architecture-modular%20domain-green.svg)](#-architecture--modular-domain-layout)
[![Data Quality](https://img.shields.io/badge/QA-IQR%20%2B%20Z--Score-orange.svg)](#-statistical-quality-assurance--anomaly-firewall)
[![Analytics](https://img.shields.io/badge/SQL-CTEs%20%26%20Window%20Functions-purple.svg)](#-advanced-commercial-sql-analytics)

An enterprise-grade commercial analytics and automated data quality engineering pipeline for pharmaceutical distribution networks. 

It acts as an automated **commercial data firewall** between raw point-of-sale (POS) transactional records and downstream executive data warehouses—transforming wide-format inventory matrices, isolating anomalies (discontinued drugs, POS glitches, negative sales), calculating statistical outlier profiles (IQR & Z-score), and loading high-integrity relational tables with sub-second analytical indexing.

---

## 🏢 Business Case & Commercial Problem Statement

### The Problem
Regional pharmaceutical supply chains receive daily sales feeds from hundreds of independent pharmacy franchises. Without automated validation gates:
- **Corrupted POS Feeds**: Terminal glitches inject negative sales quantities or malformed timestamps.
- **Catalog Non-Compliance**: Franchises log unauthorized or discontinued ATC active substances.
- **Fat-Finger Entry Skews**: Extreme statistical outliers (e.g., ringing up 10,000 units instead of 10) distort demand forecasting and supply planning.
- **Silent Dropping Failures**: Legacy ETL pipelines silently drop records, leaving operations teams blind to root-cause data loss.

### The Solution
`pharma-commercial-data-engine` implements an enterprise-grade pipeline that:
1. **Unpivots & Normalizes**: Automatically transforms wide ATC matrices into relational transactional logs using vectorized operations.
2. **Enforces Anomaly Firewalls**: Identifies non-catalog drugs, negative sales, and corrupted timestamps.
3. **Audits Statistical Quality**: Calculates Z-scores and Interquartile Ranges (IQR) per drug category, writing detailed profiles to `logs/audit_metrics.json`.
4. **Relational Warehousing**: Safely ingests validated transactions into SQLite via Python's `with DatabaseSession() as conn:` context manager pattern.
5. **Generates Root-Cause Artifacts**: Generates operational CSV rejections and executive JSON metrics for POS franchise auditing.
6. **Commercial Analytics**: Provides production CTE and Window SQL queries for category market share, MoM growth, and 7-day rolling moving averages.

---

## 📂 Architecture & Modular Domain Layout

```
pharma-commercial-data-engine/
├── core/                       # Core infrastructure & configuration
│   ├── __init__.py
│   ├── config.py              # Typed configuration dataclasses & JSON loader
│   ├── logging_setup.py       # Enterprise structured logging setup
│   └── database.py            # DatabaseSession context manager & connection pool
├── pipeline/                   # Commercial pipeline domain modules
│   ├── __init__.py
│   ├── extractor.py           # CommercialDataExtractor (raw transactional ingestion)
│   ├── transformer.py         # DrugVolumeTransformer (vectorized wide-to-long normalization)
│   ├── validator.py           # SalesAnomalyDetector & DataQualityAuditor (IQR & Z-score)
│   └── warehouse.py           # CommercialDataWarehouse & CommercialAnalyticsEngine
├── sql/                        # Relational definitions & analytical queries
│   ├── schema.sql             # DDL table creation for daily_sales
│   ├── indexes.sql            # Performance indexes on date, ATC code, and periods
│   └── analytics.sql          # Advanced CTEs & Window functions (Market share, MoM, Rolling avg)
├── app/                        # Executive visualization & operations interface
│   ├── __init__.py
│   └── dashboard.py           # Streamlit commercial analytics & QA monitoring app
├── data_raw/                   # Raw daily sales extracts (e.g., salesdaily.csv)
├── data_clean/                 # Staging clean analytical datasets
├── logs/                       # Audit metrics, QA summaries, rejections CSV, and runtime logs
└── main.py                     # Master pipeline orchestrator entrypoint
```

---

## 🛡️ Statistical Quality Assurance & Anomaly Firewall

The engine separates business-rule anomalies from statistical distribution outliers:

1. **Deterministic Rule Validation (`SalesAnomalyDetector`)**:
   - **Catalog Integrity**: Checks against authorized Anatomical Therapeutic Chemical (ATC) codes:
     `M01AB`, `M01AE`, `N02BA`, `N02BE`, `N05B`, `N05C`, `R03`, `R06`.
   - **Non-Negative Sales**: Flags negative units sold (flagged as `"Negative Sales"`).
   - **Temporal Validity**: Validates ISO date formats (flagged as `"Invalid Date Format"`).

2. **Statistical Outlier Auditing (`DataQualityAuditor`)**:
   - **Z-Score Outlier Filtering**: Identifies records exceeding $|z| > 3.0$ standard deviations within each ATC category group.
   - **IQR Distribution Profiling**: Computes $Q_1$, $Q_3$, $\text{IQR} = Q_3 - Q_1$, and bounds $[Q_1 - 1.5 \times \text{IQR}, Q_3 + 1.5 \times \text{IQR}]$ for every drug category.
   - **Comprehensive Artifact Generation**:
     - `logs/audit_metrics.json`: Complete statistical breakdown, quartile thresholds, and anomaly distributions.
     - `logs/qa_summary.json`: High-level row counts and retention rate metrics.
     - `logs/qa_rejections.csv`: Granular row-by-row quarantine file with root-cause flags.

---

## 📊 Advanced Commercial SQL Analytics

The script [`sql/analytics.sql`](sql/analytics.sql) contains production analytical queries leveraging Common Table Expressions (CTEs) and Window Functions:

### 1. Category Market Share % Over Time
Computes the monthly market volume for each ATC code and calculates its share against the total pharmaceutical volume for that month:
```sql
WITH monthly_category_sales AS (
    SELECT anio, mes, codigo_atc, SUM(cantidad_vendida) AS category_volume
    FROM daily_sales
    GROUP BY anio, mes, codigo_atc
)
SELECT 
    anio, mes, codigo_atc,
    ROUND(category_volume, 2) AS category_volume,
    ROUND(SUM(category_volume) OVER(PARTITION BY anio, mes), 2) AS total_market_volume,
    ROUND((category_volume * 100.0) / SUM(category_volume) OVER(PARTITION BY anio, mes), 2) AS market_share_percentage
FROM monthly_category_sales
ORDER BY anio, mes, category_volume DESC;
```

### 2. Month-over-Month (MoM) Volume Growth
Utilizes `LAG()` to calculate the prior month's sales velocity and net growth percentage per drug category:
```sql
WITH monthly_sales_aggregate AS (
    SELECT anio, mes, codigo_atc, SUM(cantidad_vendida) AS total_sales
    FROM daily_sales
    GROUP BY anio, mes, codigo_atc
),
mom_lag_window AS (
    SELECT 
        anio, mes, codigo_atc, total_sales,
        LAG(total_sales, 1) OVER (PARTITION BY codigo_atc ORDER BY anio, mes) AS prev_month_sales
    FROM monthly_sales_aggregate
)
SELECT 
    anio, mes, codigo_atc,
    ROUND(total_sales, 2) AS current_month_volume,
    ROUND(prev_month_sales, 2) AS previous_month_volume,
    CASE 
        WHEN prev_month_sales IS NULL OR prev_month_sales = 0 THEN 0.0
        ELSE ROUND(((total_sales - prev_month_sales) * 100.0) / prev_month_sales, 2)
    END AS mom_growth_percentage
FROM mom_lag_window;
```

### 3. 7-Day Rolling Moving Average of Volume
Uses physical framing (`ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`) to compute daily smoothed demand velocity:
```sql
WITH daily_portfolio_volume AS (
    SELECT fecha AS sale_date, SUM(cantidad_vendida) AS total_daily_volume
    FROM daily_sales
    GROUP BY fecha
)
SELECT 
    sale_date,
    ROUND(total_daily_volume, 2) AS daily_volume,
    ROUND(AVG(total_daily_volume) OVER (
        ORDER BY sale_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_7day_avg_volume
FROM daily_portfolio_volume
ORDER BY sale_date;
```

---

## ⚡ Database Session Context Manager

The SQLite data warehouse connection is fully abstracted using Python's context manager protocol (`core/database.py`):

```python
from core.database import DatabaseSession

with DatabaseSession("pharma_sales.db") as conn:
    # Automatic transaction handling: commits on clean exit, rolls back on error
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM daily_sales")
    count = cursor.fetchone()[0]
```

---

## 🚀 Execution & Quickstart

### 1. Environment Setup
Ensure Python 3.10+ is available. Activate your virtual environment and install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run the Commercial Data Pipeline
Executes extraction, transformation, anomaly detection, statistical audit, and SQLite database load:
```bash
python main.py
```

### 3. Launch the Commercial Analytics Dashboard
Start the Streamlit 2026-compliant reporting dashboard:
```bash
streamlit run app/dashboard.py
```
*(Note: All Plotly visualizations strictly use `width="stretch"` in compliance with modern Streamlit standards).*

---

## 📖 ATC Classification System Reference

| ATC Code | Therapeutic Category | Reference Active Substances |
| :--- | :--- | :--- |
| **M01AB** | Anti-inflammatory / Antirheumatic (Acetic acid derivatives) | Diclofenac, Indometacin |
| **M01AE** | Anti-inflammatory / Antirheumatic (Propionic acid derivatives) | Ibuprofen, Ketoprofen |
| **N02BA** | Other Analgesics and Antipyretics (Salicylic acid) | Aspirin |
| **N02BE** | Other Analgesics and Antipyretics (Anilides) | Paracetamol (Acetaminophen) |
| **N05B** | Psycholeptics: Anxiolytics | Diazepam, Alprazolam |
| **N05C** | Psycholeptics: Hypnotics and Sedatives | Melatonin, Zolpidem |
| **R03** | Drugs for Obstructive Airway Diseases | Salbutamol (Inhalers) |
| **R06** | Antihistamines for Systemic Use | Loratadine, Cetirizine |
