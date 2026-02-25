"""Tests for the temp file cleanup module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from backend.cleanup import cleanup_tmp_files


class TestCleanupTmpFiles:
    """Tests for cleanup_tmp_files."""

    def test_deletes_old_files(self, tmp_path: Path) -> None:
        """Files older than max_age_seconds should be deleted."""
        old_file = tmp_path / "old_export.zip"
        old_file.write_text("old data")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        import os
        os.utime(old_file, (old_time, old_time))

        deleted = cleanup_tmp_files(tmp_path, max_age_seconds=3600)
        assert deleted == 1
        assert not old_file.exists()

    def test_preserves_recent_files(self, tmp_path: Path) -> None:
        """Files newer than max_age_seconds should not be deleted."""
        recent_file = tmp_path / "recent_export.zip"
        recent_file.write_text("recent data")

        deleted = cleanup_tmp_files(tmp_path, max_age_seconds=3600)
        assert deleted == 0
        assert recent_file.exists()

    def test_mixed_old_and_new(self, tmp_path: Path) -> None:
        """Only old files should be deleted, recent ones preserved."""
        import os

        old_file = tmp_path / "old.zip"
        old_file.write_text("old")
        old_time = time.time() - 7200
        os.utime(old_file, (old_time, old_time))

        new_file = tmp_path / "new.zip"
        new_file.write_text("new")

        deleted = cleanup_tmp_files(tmp_path, max_age_seconds=3600)
        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_nonexistent_directory(self) -> None:
        """Should return 0 for non-existent directory."""
        deleted = cleanup_tmp_files(Path("/nonexistent/path"), max_age_seconds=3600)
        assert deleted == 0

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Should return 0 for empty directory."""
        deleted = cleanup_tmp_files(tmp_path, max_age_seconds=3600)
        assert deleted == 0

    def test_skips_subdirectories(self, tmp_path: Path) -> None:
        """Should not delete subdirectories."""
        import os

        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()
        old_time = time.time() - 7200
        os.utime(sub_dir, (old_time, old_time))

        deleted = cleanup_tmp_files(tmp_path, max_age_seconds=3600)
        assert deleted == 0
        assert sub_dir.exists()
