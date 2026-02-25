"""Orphaned temp file cleanup for /data/tmp/.

Provides startup cleanup (delete files older than 1 hour) and a periodic
background task (every 30 minutes) for long-running servers.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger("cheng.cleanup")

# Authoritative temp directory — imported from the export module so that
# cleanup and export always reference the same path (#262, #276).
from backend.export.package import EXPORT_TMP_DIR as DEFAULT_TMP_DIR  # noqa: E402

# Files older than this (seconds) are considered orphaned.
MAX_AGE_SECONDS = 3600  # 1 hour

# Periodic cleanup interval (seconds).
CLEANUP_INTERVAL_SECONDS = 1800  # 30 minutes


def cleanup_tmp_files(
    tmp_dir: Path = DEFAULT_TMP_DIR,
    max_age_seconds: float = MAX_AGE_SECONDS,
) -> int:
    """Delete files in tmp_dir older than max_age_seconds.

    Returns the number of files deleted.  Skips directories and files
    that cannot be deleted (e.g. permission errors).
    """
    if not tmp_dir.is_dir():
        return 0

    now = time.time()
    deleted = 0

    for p in tmp_dir.iterdir():
        if not p.is_file():
            continue
        try:
            age = now - p.stat().st_mtime
            if age > max_age_seconds:
                p.unlink()
                deleted += 1
                logger.debug("Deleted orphaned temp file: %s (age=%.0fs)", p.name, age)
        except OSError as exc:
            logger.debug("Could not delete temp file %s: %s", p.name, exc)

    if deleted:
        logger.info("Cleaned up %d orphaned temp file(s) from %s", deleted, tmp_dir)

    return deleted


async def periodic_cleanup(
    tmp_dir: Path = DEFAULT_TMP_DIR,
    interval: float = CLEANUP_INTERVAL_SECONDS,
    max_age_seconds: float = MAX_AGE_SECONDS,
) -> None:
    """Run cleanup_tmp_files periodically in a background task.

    This coroutine runs forever (until cancelled) and is intended to be
    started during the application lifespan.
    """
    import anyio

    while True:
        await anyio.sleep(interval)
        try:
            # Run blocking I/O in a worker thread to avoid blocking the event loop
            await anyio.to_thread.run_sync(cleanup_tmp_files, tmp_dir, max_age_seconds)
        except Exception:
            logger.exception("Periodic temp cleanup failed")
