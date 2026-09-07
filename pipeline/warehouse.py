"""Data warehousing and master orchestration for pharma-commercial-data-engine.
Implements CommercialDataWarehouse and CommercialAnalyticsEngine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd

from core.config import PipelineConfig, load_config
from core.database import DatabaseSession, execute_sql_script, query_to_dataframe
from core.logging_setup import get_logger, setup_logging
from pipeline.extractor import CommercialDataExtractor
from pipeline.transformer import DrugVolumeTransformer
from pipeline.validator import DataQualityAuditor, SalesAnomalyDetector, ValidationResult

logger = get_logger("pipeline.warehouse")


class CommercialDataWarehouse:
    """Manages SQLite commercial data warehouse operations, schema execution,

    bulk staging, and analytical queries using Python's DatabaseSession context manager.
    """

    def __init__(self, db_path: str | Path = "pharma_sales.db", table_name: str = "daily_sales"):
        self.db_path = str(db_path)
        self.table_name = table_name

    def initialize_schema(self, schema_path: str | Path = "sql/schema.sql") -> None:
        """Execute DDL schema creation if the schema file exists."""
        schema_file = Path(schema_path)
        if schema_file.exists():
            execute_sql_script(self.db_path, schema_file)
            logger.info(f"Database schema initialized using {schema_file}")

    def create_indexes(self, index_path: str | Path = "sql/indexes.sql") -> None:
        """Create analytical indexes if the index script file exists."""
        index_file = Path(index_path)
        if index_file.exists():
            execute_sql_script(self.db_path, index_file)
            logger.info(f"Performance indexes built using {index_file}")

    def load_clean_data(self, df_or_path: pd.DataFrame | str | Path) -> int:
        """Load clean commercial transactions into the SQLite warehouse table using DatabaseSession.

        Returns:
            The verified row count loaded into the table.
        """
        logger.info("Initializing commercial data warehouse loading process...")

        if isinstance(df_or_path, (str, Path)):
            df_clean = pd.read_csv(df_or_path)
            logger.info(f"Clean staging file read from {df_or_path} ({len(df_clean):,} records).")
        else:
            df_clean = df_or_path.copy()
            logger.info(f"Clean staging DataFrame received ({len(df_clean):,} records).")

        # Use the context manager pattern
        with DatabaseSession(self.db_path) as conn:
            logger.info(f"Writing data to the '{self.table_name}' table (full replace load)...")
            df_clean.to_sql(self.table_name, conn, if_exists="replace", index=False)
            logger.info(f"Data successfully inserted into the '{self.db_path}' database.")

            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            row_count = cursor.fetchone()[0]
            logger.info(f"Load QA: The '{self.table_name}' table has {row_count:,} stored records.")

        # Re-apply indexes after table replacement
        self.create_indexes()

        logger.info("Database connection closed safely via DatabaseSession context manager.")
        return int(row_count)

    def run_query(self, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """Execute an analytical query and return the result as a DataFrame."""
        return query_to_dataframe(self.db_path, query, params=params)


class CommercialAnalyticsEngine:
    """Master orchestrator for pharma-commercial-data-engine.

    Executes:
    1. Extraction of raw sales data.
    2. Vectorized wide-to-long transformation.
    3. Anomaly detection & catalog validation.
    4. Statistical outlier detection & audit metrics logging.
    5. Clean data export to CSV staging.
    6. Relational warehouse loading into SQLite.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or load_config()
        setup_logging(self.config.paths.log_file)

        self.extractor = CommercialDataExtractor(self.config.paths.raw_data)
        self.transformer = DrugVolumeTransformer()
        self.anomaly_detector = SalesAnomalyDetector()
        self.quality_auditor = DataQualityAuditor()
        self.warehouse = CommercialDataWarehouse(
            db_path=self.config.database.db_name,
            table_name=self.config.database.table_name,
        )

    def run(self) -> Dict[str, Any]:
        """Execute the complete commercial data engine pipeline."""
        logger.info("=" * 50)
        logger.info("STARTING MASTER PIPELINE EXECUTION")
        logger.info("=" * 50)

        # 1. Extraction
        logger.info("--- Phase 1: Extraction & QA ---")
        df_raw = self.extractor.extract()
        initial_raw_rows = len(df_raw)

        # 2. Transformation
        df_long = self.transformer.transform(df_raw)
        initial_unpivoted_rows = len(df_long)

        # 3. Rule Anomaly Detection
        df_rule_clean, rejections, audit_log = self.anomaly_detector.detect_anomalies(df_long)

        # 4. Statistical Outlier Audit (IQR / Z-Score)
        validation_result: ValidationResult = self.quality_auditor.audit_and_clean(
            df_clean=df_rule_clean,
            prior_rejections=rejections,
            prior_audit_log=audit_log,
            initial_row_count=initial_unpivoted_rows,
        )

        # 5. Export Audit Artifacts
        self.quality_auditor.export_artifacts(
            validation_result=validation_result,
            audit_metrics_path=self.config.paths.audit_metrics,
            qa_summary_path=self.config.paths.qa_summary,
            qa_rejections_path=self.config.paths.qa_rejections,
        )

        # 6. Save Clean Staging CSV
        clean_path = Path(self.config.paths.clean_data)
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        validation_result.clean_data.to_csv(clean_path, index=False)
        logger.info(f"Clean staging file generated at: {clean_path}")

        # 7. Warehouse Load
        logger.info("--- Phase 2: SQL Database Load ---")
        loaded_rows = self.warehouse.load_clean_data(validation_result.clean_data)

        logger.info("-" * 50)
        logger.info("=" * 50)
        logger.info("MASTER PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 50)

        return {
            "status": "SUCCESS",
            "raw_rows": initial_raw_rows,
            "unpivoted_rows": initial_unpivoted_rows,
            "clean_rows": len(validation_result.clean_data),
            "warehouse_rows": loaded_rows,
            "rejected_rows": validation_result.summary.get("total_rejected", 0),
            "retention_percentage": validation_result.summary.get("retention_percentage", 0.0),
        }
