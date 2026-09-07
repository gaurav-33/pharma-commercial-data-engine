"""Pharma Commercial Data Engine - Executive QA & Commercial Analytics Dashboard.
Modern Streamlit interface adhering to 2026 standards (width="stretch" for Plotly charts).
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Pharma Commercial Data Engine",
    layout="wide",
    page_icon="💊",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern enterprise aesthetics
st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 20px;
        color: #ffffff;
        border: 1px solid #334155;
        margin-bottom: 15px;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-delta {
        font-size: 0.85rem;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


BASE_DIR = Path(__file__).resolve().parent.parent


def resolve_path(rel_path: str | Path) -> Path:
    """Resolve a relative path against CWD or fallback to project BASE_DIR."""
    p = Path(rel_path)
    if p.exists():
        return p
    alt = BASE_DIR / rel_path
    return alt


@st.cache_data
def load_qa_summary() -> Dict[str, Any]:
    summary_path = resolve_path("logs/qa_summary.json")
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def load_audit_metrics() -> Dict[str, Any]:
    metrics_path = resolve_path("logs/audit_metrics.json")
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def load_rejections() -> pd.DataFrame:
    rejections_path = resolve_path("logs/qa_rejections.csv")
    if rejections_path.exists():
        return pd.read_csv(rejections_path)
    return pd.DataFrame()


@st.cache_data
def load_db_analytics(db_name: str = "pharma_sales.db") -> Dict[str, pd.DataFrame]:
    results: Dict[str, pd.DataFrame] = {}
    target_db = resolve_path(db_name)
    if not target_db.exists():
        return results

    try:
        conn = sqlite3.connect(str(target_db))

        # 1. 7-Day Rolling Moving Average query
        rolling_sql = """
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
            ROUND(AVG(total_daily_volume) OVER (
                ORDER BY sale_date 
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ), 2) AS rolling_7day_avg_volume
        FROM daily_portfolio_volume
        ORDER BY sale_date;
        """
        results["rolling"] = pd.read_sql_query(rolling_sql, conn)

        # 2. Market Share query
        market_share_sql = """
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
                SUM(category_volume) OVER(PARTITION BY anio, mes) AS total_monthly_market_volume
            FROM monthly_category_sales
        )
        SELECT 
            anio || '-' || printf('%02d', mes) AS period,
            codigo_atc,
            ROUND(category_volume, 2) AS category_volume,
            ROUND((category_volume * 100.0) / total_monthly_market_volume, 2) AS market_share_percentage
        FROM market_share_calculation
        ORDER BY period, category_volume DESC;
        """
        results["market_share"] = pd.read_sql_query(market_share_sql, conn)

        conn.close()
    except Exception as exc:
        st.warning(f"Unable to query analytics from database: {exc}")

    return results


# Header
st.title("💊 Pharma Commercial Data Engine")
st.markdown(
    "**Enterprise Commercial Analytics & Data Quality Assurance Dashboard**  \n"
    "Real-time visibility into the commercial data firewall, statistical quality audit (IQR/Z-Score), "
    "and pharmaceutical portfolio performance."
)

summary = load_qa_summary()
audit_metrics = load_audit_metrics()
df_rejections = load_rejections()
db_data = load_db_analytics()

if not summary:
    st.error("Pipeline audit artifacts not found. Please execute `python main.py` to run the engine first.")
    st.stop()

# --- Top Level Executive KPIs ---
st.markdown("### Executive QA & Pipeline Summary")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

initial_rows = summary.get("initial_rows", 0)
final_rows = summary.get("final_rows", 0)
total_rejected = summary.get("total_rejected", 0)
retention_pct = summary.get("retention_percentage", 0.0)

kpi1.metric("Raw Transaction Records", f"{initial_rows:,}")
kpi2.metric("Clean Records Warehouse-Ready", f"{final_rows:,}")
kpi3.metric("Quarantined Anomaly Records", f"{total_rejected:,}", delta=f"-{total_rejected} flagged", delta_color="inverse")
kpi4.metric("Pipeline Data Retention", f"{retention_pct}%")

st.divider()

# --- Interactive Tabs ---
tab_qa, tab_audit, tab_analytics, tab_explorer = st.tabs([
    "🛡️ QA Firewall & Rejections",
    "📊 Statistical Quality Audit (IQR & Z-Score)",
    "📈 Commercial Trends & Rolling Volume",
    "🔍 Rejections Deep-Dive Explorer",
])

# --- TAB 1: QA Firewall ---
with tab_qa:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Anomalies by Classification")
        if not df_rejections.empty:
            rejection_counts = df_rejections["rejection_reason"].value_counts()
            for reason, count in rejection_counts.items():
                st.metric(label=f"⚠️ {reason}", value=f"{count:,} records")
        else:
            st.success("No anomalies detected across all validation gates.")

    with col_right:
        st.subheader("Quarantined Records by ATC Category")
        if not df_rejections.empty and "codigo_atc" in df_rejections.columns:
            atc_counts = df_rejections.groupby("codigo_atc").size().reset_index(name="Count")
            atc_counts = atc_counts.sort_values("Count", ascending=True)

            fig_atc = px.bar(
                atc_counts,
                x="Count",
                y="codigo_atc",
                orientation="h",
                text="Count",
                color="Count",
                color_continuous_scale="Reds",
                title="Quarantined Records per Drug Category",
            )
            fig_atc.update_traces(textposition="outside")
            fig_atc.update_layout(
                xaxis_title="Quarantined Rows",
                yaxis_title="ATC Code",
                margin=dict(t=30, b=0, l=0, r=0),
                coloraxis_showscale=False,
            )
            # 2026 Streamlit standard: width="stretch"
            st.plotly_chart(fig_atc, width="stretch")
        else:
            st.info("No rejections available for ATC breakdown.")

    with st.expander("📝 View Pipeline Execution Audit Log"):
        logs = summary.get("audit_log", [])
        if logs:
            for entry in logs:
                st.write(f"- {entry}")
        else:
            st.write("No audit entries recorded.")

# --- TAB 2: Statistical Quality Audit ---
with tab_audit:
    st.subheader("Statistical Profiles & Outlier Analysis per Drug Category")
    st.markdown(
        "Encapsulated inside `DataQualityAuditor`. Analyzes sales volume distributions using both "
        "**Z-Score (|z| > 3.0)** and **Interquartile Range (IQR, 1.5 multiplier)**."
    )

    profiles = audit_metrics.get("atc_profiles", {})
    if profiles:
        profile_rows = []
        for code, prof in profiles.items():
            profile_rows.append({
                "ATC Code": code,
                "Records": prof.get("record_count"),
                "Mean Sales": prof.get("mean"),
                "Std Dev": prof.get("std"),
                "Median": prof.get("median"),
                "Q1 (25%)": prof.get("q25"),
                "Q3 (75%)": prof.get("q75"),
                "IQR": prof.get("iqr"),
                "IQR Lower Bound": prof.get("lower_bound_iqr"),
                "IQR Upper Bound": prof.get("upper_bound_iqr"),
                "Z-Score Outliers": prof.get("z_outliers_count"),
                "IQR Outliers": prof.get("iqr_outliers_count"),
            })

        df_profiles = pd.DataFrame(profile_rows)
        st.dataframe(df_profiles, hide_index=True)

        # Comparative Bar Chart: Z-Score vs IQR Outliers
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=df_profiles["ATC Code"],
            y=df_profiles["Z-Score Outliers"],
            name="Z-Score Outliers (|z| > 3)",
            marker_color="#38bdf8",
        ))
        fig_comp.add_trace(go.Bar(
            x=df_profiles["ATC Code"],
            y=df_profiles["IQR Outliers"],
            name="IQR Outliers (1.5x IQR)",
            marker_color="#f97316",
        ))
        fig_comp.update_layout(
            title="Comparison of Outlier Counts: Z-Score vs IQR Thresholds",
            barmode="group",
            xaxis_title="ATC Category",
            yaxis_title="Detected Outlier Count",
            margin=dict(t=40, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_comp, width="stretch")
    else:
        st.info("Statistical profiles not available in audit_metrics.json.")

# --- TAB 3: Commercial Analytics ---
with tab_analytics:
    st.subheader("Commercial Performance & Demand Velocity")
    st.markdown(
        "Computed via Window Functions (`AVG() OVER`, `SUM() OVER`) in `sql/analytics.sql`."
    )

    if "rolling" in db_data and not db_data["rolling"].empty:
        df_rolling = db_data["rolling"].copy()
        df_rolling["sale_date"] = pd.to_datetime(df_rolling["sale_date"])

        fig_rolling = go.Figure()
        fig_rolling.add_trace(go.Scatter(
            x=df_rolling["sale_date"],
            y=df_rolling["daily_volume"],
            mode="lines",
            name="Daily Volume",
            line=dict(color="#64748b", width=1),
            opacity=0.5,
        ))
        fig_rolling.add_trace(go.Scatter(
            x=df_rolling["sale_date"],
            y=df_rolling["rolling_7day_avg_volume"],
            mode="lines",
            name="7-Day Rolling Moving Average",
            line=dict(color="#06b6d4", width=2.5),
        ))
        fig_rolling.update_layout(
            title="Commercial Volume & 7-Day Rolling Moving Average Over Time",
            xaxis_title="Sale Date",
            yaxis_title="Sales Quantity Sold",
            margin=dict(t=40, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_rolling, width="stretch")

    if "market_share" in db_data and not db_data["market_share"].empty:
        df_ms = db_data["market_share"].copy()
        fig_ms = px.bar(
            df_ms,
            x="period",
            y="market_share_percentage",
            color="codigo_atc",
            title="Monthly Category Market Share % Over Time (Window Partitioned)",
            labels={"period": "Year-Month", "market_share_percentage": "Market Share %", "codigo_atc": "ATC Code"},
        )
        fig_ms.update_layout(
            barmode="stack",
            yaxis_title="Market Share %",
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_ms, width="stretch")

# --- TAB 4: Rejections Explorer ---
with tab_explorer:
    st.subheader("Point-of-Sale Rejections Deep-Dive Explorer")
    st.markdown(
        "Investigate flagged records to trace POS configuration errors or franchise integration bugs."
    )

    if not df_rejections.empty:
        reasons = ["All"] + sorted(df_rejections["rejection_reason"].dropna().unique().tolist())
        selected_reason = st.selectbox("Filter by Anomaly Type", reasons)

        filtered_df = df_rejections
        if selected_reason != "All":
            filtered_df = df_rejections[df_rejections["rejection_reason"] == selected_reason]

        st.dataframe(filtered_df, hide_index=True)

        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Filtered Anomalies (CSV)",
            data=csv_data,
            file_name="quarantined_records_export.csv",
            mime="text/csv",
        )
    else:
        st.success("No rejected records to display.")
