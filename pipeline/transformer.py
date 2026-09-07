"""Drug volume transformer for pharmaceutical commercial records.
Performs vectorized wide-to-long normalization and schema standardization.
"""

from __future__ import annotations

from typing import List, Optional
import pandas as pd

from core.logging_setup import get_logger

logger = get_logger("pipeline.transformer")


class DrugVolumeTransformer:
    """Transforms wide-format pharmaceutical inventory/sales matrices into normalized

    commercial transaction records suitable for relational data warehousing.
    """

    DEFAULT_ID_VARS: List[str] = ["datum", "Year", "Month", "Hour", "Weekday Name"]
    COLUMN_MAPPING = {
        "datum": "fecha",
        "Year": "anio",
        "Month": "mes",
        "Hour": "hora",
        "Weekday Name": "dia_semana",
    }

    def __init__(self, id_vars: Optional[List[str]] = None):
        self.id_vars = id_vars or self.DEFAULT_ID_VARS

    def transform(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Execute vectorized unpivot (wide-to-long melt) and standardize column schemas.

        Args:
            df_raw: Raw DataFrame loaded from the commercial sales extract.

        Returns:
            Normalized DataFrame with standardized column names and parsed dates.
        """
        logger.info("Transforming commercial data from wide to long format (unpivot)...")

        # Determine medication columns using clean list comprehension
        value_vars = [col for col in df_raw.columns if col not in self.id_vars]
        existing_id_vars = [col for col in self.id_vars if col in df_raw.columns]

        # Vectorized melt operation
        df_long = pd.melt(
            df_raw,
            id_vars=existing_id_vars,
            value_vars=value_vars,
            var_name="codigo_atc",
            value_name="cantidad_vendida",
        )

        # Standardize column naming conventions
        df_long = df_long.rename(columns=self.COLUMN_MAPPING)

        # Vectorized date normalization
        if "fecha" in df_long.columns:
            df_long["fecha"] = pd.to_datetime(df_long["fecha"], errors="coerce")

        logger.info(
            f"Transformation completed: {len(df_long):,} records generated from {len(df_raw):,} raw rows."
        )
        return df_long
