"""Commercial sales validation, anomaly detection, and data quality auditing.
Encapsulates master catalog verification, transactional rules, and IQR/Z-score metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from core.logging_setup import get_logger

logger = get_logger("pipeline.validator")

# Master Catalog of authorized ATC pharmaceutical category codes
ALLOWED_ATC_CODES: List[str] = [
    "M01AB",  # Anti-inflammatory / Antirheumatic (Non-Steroids)
    "M01AE",  # Anti-inflammatory / Antirheumatic (Propionic Acid)
    "N02BA",  # Other Analgesics and Antipyretics (Salicylic Acid)
    "N02BE",  # Other Analgesics and Antipyretics (Anilides)
    "N05B",   # Anxiolytics
    "N05C",   # Hypnotics and Sedatives
    "R03",    # Drugs for Obstructive Airway Diseases
    "R06",    # Antihistamines for Systemic Use
]


@dataclass
class ValidationResult:
    """Encapsulates the output of the data quality validation and auditing process."""

    clean_data: pd.DataFrame
    rejections: pd.DataFrame
    summary: Dict[str, Any]
    audit_metrics: Dict[str, Any]
    audit_log: List[str] = field(default_factory=list)


class SalesAnomalyDetector:
    """Identifies rule-based business anomalies in commercial sales transactions."""

    def __init__(self, allowed_atc_codes: Optional[List[str]] = None):
        self.allowed_atc_codes = allowed_atc_codes or ALLOWED_ATC_CODES

    def detect_anomalies(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[pd.DataFrame], List[str]]:
        """Run deterministic rule validations against commercial records.

        Validations performed:
        1. Master catalog authorization (unauthorized ATC codes).
        2. Transactional value sanity (negative sales quantity).
        3. Temporal integrity (invalid/null dates).

        Returns:
            Tuple of (surviving_df, list_of_rejection_dataframes, audit_log_messages).
        """
        df_current = df.copy()
        rejections: List[pd.DataFrame] = []
        audit_log: List[str] = []

        # 1. Master Catalog Validation
        invalid_atc_mask = ~df_current["codigo_atc"].isin(self.allowed_atc_codes)
        if invalid_atc_mask.any():
            invalid_atc_rows = df_current[invalid_atc_mask].copy()
            invalid_atc_rows["rejection_reason"] = "Invalid ATC Code"
            rejections.append(invalid_atc_rows)
            df_current = df_current[~invalid_atc_mask]
            msg = f"Removed {len(invalid_atc_rows)} records with invalid ATC codes."
            audit_log.append(msg)
            logger.warning(msg)

        # 2. Check for negative sales quantities (point-of-sale refund/system error)
        negative_sales_mask = df_current["cantidad_vendida"] < 0
        if negative_sales_mask.any():
            negative_sales_rows = df_current[negative_sales_mask].copy()
            negative_sales_rows["rejection_reason"] = "Negative Sales"
            rejections.append(negative_sales_rows)
            df_current = df_current[~negative_sales_mask]
            msg = f"Removed {len(negative_sales_rows)} records with negative sales (possible system error)."
            audit_log.append(msg)
            logger.warning(msg)

        # 3. Format & validate dates
        if not pd.api.types.is_datetime64_any_dtype(df_current["fecha"]):
            df_current["fecha"] = pd.to_datetime(df_current["fecha"], errors="coerce")

        null_dates_mask = df_current["fecha"].isna()
        if null_dates_mask.any():
            null_dates_rows = df_current[null_dates_mask].copy()
            null_dates_rows["rejection_reason"] = "Invalid Date Format"
            rejections.append(null_dates_rows)
            df_current = df_current[~null_dates_mask]
            msg = f"Removed {len(null_dates_rows)} records with invalid date format."
            audit_log.append(msg)
            logger.warning(msg)

        return df_current, rejections, audit_log


class DataQualityAuditor:
    """Encapsulates statistical outlier detection (Z-Score and IQR) and generates

    commercial analytics quality metrics.
    """

    def __init__(self, z_threshold: float = 3.0, iqr_multiplier: float = 1.5):
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier

    def compute_z_scores(
        self, df: pd.DataFrame, group_col: str = "codigo_atc", val_col: str = "cantidad_vendida"
    ) -> pd.Series:
        """Vectorized Z-Score calculation grouped by category."""
        with np.errstate(divide="ignore", invalid="ignore"):
            return df.groupby(group_col)[val_col].transform(
                lambda x: (x - x.mean()) / (x.std() if x.std() != 0 and not pd.isna(x.std()) else 1.0)
            )

    def compute_statistical_profiles(
        self, df: pd.DataFrame, group_col: str = "codigo_atc", val_col: str = "cantidad_vendida"
    ) -> Dict[str, Dict[str, Any]]:
        """Compute IQR distributions, bounds, and Z-Score statistics for each drug category."""
        profiles: Dict[str, Dict[str, Any]] = {}

        for code, group in df.groupby(group_col):
            vals = group[val_col].dropna()
            count = int(len(vals))
            if count == 0:
                continue

            q25 = float(np.percentile(vals, 25))
            q75 = float(np.percentile(vals, 75))
            iqr = float(q75 - q25)
            lower_bound_iqr = float(q25 - (self.iqr_multiplier * iqr))
            upper_bound_iqr = float(q75 + (self.iqr_multiplier * iqr))

            mean_val = float(vals.mean())
            std_val = float(vals.std()) if count > 1 else 0.0
            median_val = float(vals.median())

            # Z-Score bounds and counts
            if std_val > 0:
                z_scores = (vals - mean_val) / std_val
                z_outliers = int((np.abs(z_scores) > self.z_threshold).sum())
            else:
                z_outliers = 0

            iqr_outliers = int(((vals < lower_bound_iqr) | (vals > upper_bound_iqr)).sum())

            profiles[str(code)] = {
                "record_count": count,
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "median": round(median_val, 4),
                "q25": round(q25, 4),
                "q75": round(q75, 4),
                "iqr": round(iqr, 4),
                "lower_bound_iqr": round(lower_bound_iqr, 4),
                "upper_bound_iqr": round(upper_bound_iqr, 4),
                "z_threshold": self.z_threshold,
                "z_outliers_count": z_outliers,
                "iqr_outliers_count": iqr_outliers,
            }

        return profiles

    def audit_and_clean(
        self,
        df_clean: pd.DataFrame,
        prior_rejections: List[pd.DataFrame],
        prior_audit_log: List[str],
        initial_row_count: int,
    ) -> ValidationResult:
        """Run statistical outlier detection, assemble audit metrics, and compile final deliverables."""
        logger.info("Starting statistical outlier detection & data quality audit...")

        # Compute statistical profiles per ATC code prior to outlier removal
        atc_profiles = self.compute_statistical_profiles(df_clean)

        # Detect statistical outliers using Z-score by ATC code
        df_audited = df_clean.copy()
        df_audited["z_score"] = self.compute_z_scores(df_audited)

        outliers_mask = df_audited["z_score"].abs() > self.z_threshold
        outliers_rows = df_audited[outliers_mask].copy()

        rejections_list = list(prior_rejections)
        audit_log = list(prior_audit_log)

        if not outliers_rows.empty:
            outliers_rows["rejection_reason"] = f"Statistical Outlier (Z-Score > {int(self.z_threshold)})"
            rejections_list.append(outliers_rows)
            df_audited = df_audited[~outliers_mask]
            msg = f"Removed {len(outliers_rows)} records identified as statistical outliers."
            audit_log.append(msg)
            logger.warning(msg)

        # Drop temporary z_score column from clean data and rejections
        df_audited = df_audited.drop(columns=["z_score"], errors="ignore")
        cleaned_rejections_list = []
        for r in rejections_list:
            r_copy = r.drop(columns=["z_score"], errors="ignore").copy()
            cleaned_rejections_list.append(r_copy)

        final_rows = len(df_audited)
        total_rejected = sum(len(r) for r in cleaned_rejections_list) if cleaned_rejections_list else 0
        retention_pct = round((final_rows / initial_row_count) * 100, 2) if initial_row_count > 0 else 0.0

        if cleaned_rejections_list:
            df_rejections = pd.concat(cleaned_rejections_list, ignore_index=True)
            rejection_reasons_dist = df_rejections["rejection_reason"].value_counts().to_dict()
        else:
            df_rejections = pd.DataFrame()
            rejection_reasons_dist = {}

        # Construct legacy qa_summary (for backward compatibility with dashboard & tests)
        qa_summary: Dict[str, Any] = {
            "initial_rows": initial_row_count,
            "final_rows": final_rows,
            "total_rejected": total_rejected,
            "retention_percentage": retention_pct,
            "audit_log": audit_log,
        }

        # Construct production audit_metrics
        audit_metrics: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "initial_rows": initial_row_count,
            "final_rows": final_rows,
            "total_rejected": total_rejected,
            "retention_percentage": retention_pct,
            "z_threshold": self.z_threshold,
            "iqr_multiplier": self.iqr_multiplier,
            "rejection_breakdown": rejection_reasons_dist,
            "atc_profiles": atc_profiles,
            "audit_log": audit_log,
        }

        logger.info(f"QA Audit Report Summary: Final structure: {final_rows:,} rows, {df_audited.shape[1]} columns")
        logger.info(f"Retention percentage: {retention_pct}% ({total_rejected} quarantined)")

        return ValidationResult(
            clean_data=df_audited,
            rejections=df_rejections,
            summary=qa_summary,
            audit_metrics=audit_metrics,
            audit_log=audit_log,
        )

    def export_artifacts(
        self,
        validation_result: ValidationResult,
        audit_metrics_path: str | Path = "logs/audit_metrics.json",
        qa_summary_path: str | Path = "logs/qa_summary.json",
        qa_rejections_path: str | Path = "logs/qa_rejections.csv",
    ) -> None:
        """Write out audit metrics, QA summary, and rejections CSV reports."""
        metrics_p = Path(audit_metrics_path)
        metrics_p.parent.mkdir(parents=True, exist_ok=True)

        with open(metrics_p, "w", encoding="utf-8") as f:
            json.dump(validation_result.audit_metrics, f, indent=4)
        logger.info(f"Audit Metrics JSON generated at: {metrics_p}")

        summary_p = Path(qa_summary_path)
        summary_p.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_p, "w", encoding="utf-8") as f:
            json.dump(validation_result.summary, f, indent=4)
        logger.info(f"QA Summary JSON generated at: {summary_p}")

        rejections_p = Path(qa_rejections_path)
        rejections_p.parent.mkdir(parents=True, exist_ok=True)
        if not validation_result.rejections.empty:
            validation_result.rejections.to_csv(rejections_p, index=False)
            logger.info(f"QA Rejections Report generated at: {rejections_p}")
        elif rejections_p.exists():
            # If no rejections, empty file with schema header
            pd.DataFrame(
                columns=[
                    "fecha",
                    "anio",
                    "mes",
                    "hora",
                    "dia_semana",
                    "codigo_atc",
                    "cantidad_vendida",
                    "rejection_reason",
                ]
            ).to_csv(rejections_p, index=False)
