"""
scripts/export_corrections.py
==============================
Export the human corrections dataset from the `corrections` table.

Output is JSONL (one JSON object per line), suitable for:
  - Fine-tuning or prompt-tuning future address parsing models
  - Expanding the gold test set in tests/test_pipeline.py
  - Building a training dataset for supervised geocoding

Usage:
    python scripts/export_corrections.py [--output corrections.jsonl] [--limit 10000]

Each output line contains:
  {
    "id": "<uuid>",
    "request_id": "<uuid>",
    "reviewer_id": "<string>",
    "reviewed_at": "<iso8601>",
    "original_lat": <float|null>,
    "original_lng": <float|null>,
    "corrected_lat": <float|null>,
    "corrected_lng": <float|null>,
    "original_parsed": {<structured fields>},
    "corrected_parsed": {<structured fields>|null},
    "correction_notes": "<string|null>",
    "turnaround_seconds": <float|null>
  }

Privacy note: corrected_parsed may contain human-entered address tokens.
Apply the same DPDP Act data handling as raw_address_staging.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def export_corrections(output_path: str = "corrections.jsonl", limit: int = 10000) -> int:
    """
    Export corrections from database to JSONL file.
    Returns the number of records exported.
    """
    from persistence.database import init_db, SessionLocal
    from persistence.repository import get_corrections_for_export

    init_db()
    db = SessionLocal()

    try:
        logger.info("Fetching corrections (limit=%d)...", limit)
        records = get_corrections_for_export(db, limit=limit)
        count = len(records)

        if count == 0:
            logger.warning("No corrections found in the database. Is the review loop active?")
            return 0

        with open(output_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        logger.info(
            "Exported %d corrections to '%s'. "
            "This dataset is ready for fine-tuning or gold test-set expansion.",
            count, output_path,
        )
        return count

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Pata human corrections dataset to JSONL for fine-tuning / test-set expansion."
    )
    parser.add_argument(
        "--output",
        default="corrections.jsonl",
        help="Output file path (default: corrections.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Maximum number of records to export (default: 10000)",
    )
    args = parser.parse_args()

    try:
        count = export_corrections(output_path=args.output, limit=args.limit)
        if count > 0:
            logger.info("Export complete. Statistics:")
            # Print schema as a hint for consumers
            logger.info(
                "Fields: id, request_id, reviewer_id, reviewed_at, "
                "original_lat, original_lng, corrected_lat, corrected_lng, "
                "original_parsed, corrected_parsed, correction_notes, turnaround_seconds"
            )
        sys.exit(0)
    except Exception as exc:
        logger.error("Export failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
