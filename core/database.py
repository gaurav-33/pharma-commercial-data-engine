"""Database connection session manager for SQLite data warehouse.
Implements the Python context manager protocol (`with DatabaseSession() as conn:`).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional, Type
import pandas as pd

from core.logging_setup import get_logger

logger = get_logger("core.database")


class DatabaseSession:
    """Context manager for SQLite database transactions.

    Usage:
        with DatabaseSession("pharma_sales.db") as conn:
            conn.execute("SELECT 1")
    """

    def __init__(self, db_path: str | Path = "pharma_sales.db", timeout: float = 30.0):
        self.db_path = str(db_path)
        self.timeout = timeout
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        db_dir = Path(self.db_path).parent
        if db_dir and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        # Enable foreign keys and modern SQLite optimizations
        self.conn.execute("PRAGMA foreign_keys = ON;")
        return self.conn

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        if self.conn:
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
                    logger.error(
                        f"Database transaction rolled back due to error: {exc_val}",
                        exc_info=(exc_type, exc_val, exc_tb),
                    )
            finally:
                self.conn.close()
                self.conn = None
        # Do not suppress exceptions
        return False


def execute_sql_script(db_path: str | Path, script_path: str | Path) -> None:
    """Execute a multi-statement SQL script using DatabaseSession."""
    script_file = Path(script_path)
    if not script_file.exists():
        raise FileNotFoundError(f"SQL script not found: {script_file}")

    sql_content = script_file.read_text(encoding="utf-8")
    with DatabaseSession(db_path) as conn:
        conn.executescript(sql_content)
    logger.debug(f"Executed script {script_file.name} against {db_path}")


def query_to_dataframe(db_path: str | Path, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """Execute a query within a DatabaseSession and return results as a DataFrame."""
    with DatabaseSession(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)
