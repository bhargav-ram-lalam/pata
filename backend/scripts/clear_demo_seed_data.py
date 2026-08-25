#!/usr/bin/env python3
"""
backend/scripts/clear_demo_seed_data.py
=======================================
Clears demo resolutions, staged raw addresses, and corrections from the database.
Use between rehearsal runs or before live presentations to start with a clean slate.

Usage:
    python backend/scripts/clear_demo_seed_data.py
    python backend/scripts/clear_demo_seed_data.py --all  # wipes all rows in resolutions, raw_address_staging, corrections
"""
from __future__ import annotations

import argparse
import io
import pathlib
import sys

# Force UTF-8 stdout on Windows
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure backend root on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from persistence.database import SessionLocal, init_db
from persistence.models import ResolutionModel, RawAddressStagingModel, CorrectionModel


def clear_db(wipe_all: bool = True) -> None:
    init_db()
    db = SessionLocal()
    try:
        if wipe_all:
            c_count = db.query(CorrectionModel).delete()
            s_count = db.query(RawAddressStagingModel).delete()
            r_count = db.query(ResolutionModel).delete()
            db.commit()
            print(f"✅ Cleared all database records:")
            print(f"   - {r_count} resolutions deleted")
            print(f"   - {s_count} raw address staging records deleted")
            print(f"   - {c_count} corrections deleted")
        else:
            # Delete pending_review rows
            s_pending = db.query(ResolutionModel).filter(ResolutionModel.review_status == "pending_review").all()
            p_ids = [r.request_id for r in s_pending]
            if p_ids:
                db.query(RawAddressStagingModel).filter(RawAddressStagingModel.request_id.in_(p_ids)).delete(synchronize_session=False)
                r_count = db.query(ResolutionModel).filter(ResolutionModel.request_id.in_(p_ids)).delete(synchronize_session=False)
                db.commit()
                print(f"✅ Cleared {r_count} pending_review items from queue.")
            else:
                print("ℹ️ No pending_review items to clear.")
    except Exception as e:
        db.rollback()
        print(f"❌ Error clearing database: {e}")
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset/clear Pata database demo records")
    parser.add_argument("--pending-only", action="store_true", help="Clear only pending_review rows instead of all rows")
    args = parser.parse_args()

    clear_db(wipe_all=not args.pending_only)


if __name__ == "__main__":
    main()
