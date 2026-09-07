"""Configuration management for pharma-commercial-data-engine.
Defines typed dataclasses and configuration loaders.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class PathsConfig:
    raw_data: str = "data_raw/salesdaily.csv"
    clean_data: str = "data_clean/salesdaily_clean.csv"
    log_file: str = "logs/pipeline.log"
    audit_metrics: str = "logs/audit_metrics.json"
    qa_summary: str = "logs/qa_summary.json"
    qa_rejections: str = "logs/qa_rejections.csv"


@dataclass
class DatabaseConfig:
    db_name: str = "pharma_sales.db"
    table_name: str = "daily_sales"


@dataclass
class PipelineConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paths": {
                "raw_data": self.paths.raw_data,
                "clean_data": self.paths.clean_data,
                "log_file": self.paths.log_file,
                "audit_metrics": self.paths.audit_metrics,
                "qa_summary": self.paths.qa_summary,
                "qa_rejections": self.paths.qa_rejections,
            },
            "database": {
                "db_name": self.database.db_name,
                "table_name": self.database.table_name,
            },
        }

    def __getitem__(self, item: str) -> Any:
        # Dictionary-style backward compatibility
        return self.to_dict()[item]


def load_config(config_path: str | Path = "config.json") -> PipelineConfig:
    """Load configuration from a JSON file, falling back to production defaults."""
    target_path = Path(config_path)
    if not target_path.exists():
        return PipelineConfig()

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        paths_dict = raw.get("paths", {})
        database_dict = raw.get("database", {})

        paths = PathsConfig(
            raw_data=paths_dict.get("raw_data", "data_raw/salesdaily.csv"),
            clean_data=paths_dict.get("clean_data", "data_clean/salesdaily_clean.csv"),
            log_file=paths_dict.get("log_file", "logs/pipeline.log"),
            audit_metrics=paths_dict.get("audit_metrics", "logs/audit_metrics.json"),
            qa_summary=paths_dict.get("qa_summary", "logs/qa_summary.json"),
            qa_rejections=paths_dict.get("qa_rejections", "logs/qa_rejections.csv"),
        )
        database = DatabaseConfig(
            db_name=database_dict.get("db_name", "pharma_sales.db"),
            table_name=database_dict.get("table_name", "daily_sales"),
        )
        return PipelineConfig(paths=paths, database=database)
    except Exception:
        return PipelineConfig()
