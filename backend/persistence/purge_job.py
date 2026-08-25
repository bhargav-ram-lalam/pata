"""
persistence/purge_job.py
========================
Background TTL purge worker for removing expired raw address staging records.
Can run in-process within FastAPI lifespan or standalone via CLI.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from persistence.repository import purge_expired_raw_addresses

logger = logging.getLogger(__name__)

DEFAULT_PURGE_INTERVAL_SEC = int(os.getenv("PATA_PURGE_INTERVAL_SEC", "3600"))


class PurgeWorker:
    """Async background worker that periodically triggers raw address purging."""

    def __init__(self, interval_seconds: int = DEFAULT_PURGE_INTERVAL_SEC):
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def _run_loop(self) -> None:
        logger.info("Starting TTL purge worker loop (interval: %ds)", self.interval_seconds)
        while self._running:
            try:
                purged = purge_expired_raw_addresses()
                if purged > 0:
                    logger.info("TTL Purge Worker: removed %d expired records", purged)
            except Exception as exc:
                logger.error("TTL Purge Worker error: %s", exc)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TTL Purge Worker stopped.")


# Singleton instance for in-process lifecycle
purge_worker = PurgeWorker()


def main():
    """Standalone CLI runner for cron-based execution."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Running standalone raw address staging purge...")
    try:
        purged = purge_expired_raw_addresses()
        logger.info("Purge completed successfully. Total records purged: %d", purged)
        sys.exit(0)
    except Exception as exc:
        logger.error("Standalone purge failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
