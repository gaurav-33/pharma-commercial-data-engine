"""Pharma Commercial Data Engine - Master Orchestrator Entrypoint.
Executes the production commercial data engineering and QA pipeline.
"""

from __future__ import annotations

import sys
from pipeline.warehouse import CommercialAnalyticsEngine


def main() -> int:
    """Run the commercial data analytics pipeline."""
    try:
        engine = CommercialAnalyticsEngine()
        result = engine.run()
        return 0 if result["status"] == "SUCCESS" else 1
    except Exception as exc:
        print(f"CRITICAL: Master pipeline execution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
