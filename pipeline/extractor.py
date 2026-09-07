"""Commercial data extractor for raw pharmaceutical transactional logs."""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from core.logging_setup import get_logger

logger = get_logger("pipeline.extractor")


class CommercialDataExtractor:
    """Extracts raw wide-format pharmaceutical transaction data from file storage."""

    def __init__(self, raw_data_path: str | Path = "data_raw/salesdaily.csv"):
        self.raw_data_path = Path(raw_data_path)

    def extract(self) -> pd.DataFrame:
        """Load and return the raw sales transactions DataFrame."""
        logger.info(f"Extracting raw commercial data from: {self.raw_data_path}")

        if not self.raw_data_path.exists():
            err_msg = f"Raw data file not found: {self.raw_data_path}"
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        df = pd.read_csv(self.raw_data_path)
        logger.info(f"Raw data extracted successfully: {len(df):,} records, {df.shape[1]} columns")
        return df
