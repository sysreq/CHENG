"""Tests for the storage backend layer (LocalStorage).

Covers edge cases like path traversal, missing files, corrupted JSON,
file permission errors, and atomic write behaviour.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.storage import LocalStorage


def test_safe_id_prevents_traversal() -> None:
    """_safe_id should strip directory components and reject '.' or '..'."""
    storage = LocalStorage(base_path="/tmp")

    # Should strip directory parts
    assert storage._safe_id("../../etc/passwd") == "passwd"
    assert storage._safe_id("folder/file.json") == "file.json"

    # Should reject '.' and '..'
    with pytest.raises(ValueError, match="Invalid design id"):
        storage._safe_id(".")
    with pytest.raises(ValueError, match="Invalid design id"):
        storage._safe_id("..")
    with pytest.raises(ValueError, match="Invalid design id"):
        storage._safe_id("")


def test_save_design_handles_io_error(tmp_storage: LocalStorage) -> None:
    """save_design should bubble up OS/IO errors like disk full or permissions."""
    with patch("os.replace", side_effect=OSError("No space left on device")):
        with pytest.raises(OSError, match="No space left on device"):
            tmp_storage.save_design("test-disk-full", {"id": "test-disk-full"})


def test_load_design_not_found(tmp_storage: LocalStorage) -> None:
    """load_design should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError, match="Design not found: missing-id"):
        tmp_storage.load_design("missing-id")


def test_load_design_corrupt_json(tmp_storage: LocalStorage) -> None:
    """load_design should bubble up JSONDecodeError for corrupted files."""
    path = tmp_storage._path("corrupt-id")
    path.write_text("{corrupt: json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        tmp_storage.load_design("corrupt-id")


def test_list_designs_handles_large_files(tmp_storage: LocalStorage) -> None:
    """list_designs should correctly parse files of any size."""
    long_string = "A" * 2000
    data = {"id": "large-file", "name": "Large File", "long_data": long_string}
    tmp_storage.save_design("large-file", data)

    designs = tmp_storage.list_designs()
    assert len(designs) == 1
    assert designs[0]["id"] == "large-file"
    assert designs[0]["name"] == "Large File"


def test_list_designs_skips_corrupted_files(tmp_storage: LocalStorage) -> None:
    """list_designs should gracefully skip files that cannot be parsed at all."""
    # Write a valid design
    tmp_storage.save_design("valid-design", {"id": "valid-design", "name": "Valid"})

    # Write a corrupt design
    corrupt_path = tmp_storage._path("corrupt-design")
    corrupt_path.write_text("{not: json}", encoding="utf-8")

    designs = tmp_storage.list_designs()

    # The corrupted file should be skipped, returning only the valid one
    assert len(designs) == 1
    assert designs[0]["id"] == "valid-design"


def test_list_designs_skips_unreadable_files(tmp_storage: LocalStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    """list_designs should skip files that raise OSError during read."""
    tmp_storage.save_design("unreadable", {"id": "unreadable", "name": "Unreadable"})

    # Mock read_text to raise OSError
    original_read_text = Path.read_text

    def mock_read_text(self, *args, **kwargs):
        if str(self).endswith("unreadable.cheng"):
            raise OSError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    designs = tmp_storage.list_designs()
    assert len(designs) == 0


def test_delete_design_not_found(tmp_storage: LocalStorage) -> None:
    """delete_design should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError, match="Design not found: missing-id"):
        tmp_storage.delete_design("missing-id")


# ---------------------------------------------------------------------------
# Atomic write tests (#263)
# ---------------------------------------------------------------------------


def test_save_design_atomic_success(tmp_storage: LocalStorage) -> None:
    """save_design should write correct JSON to the final file path."""
    data = {"id": "atomic-ok", "name": "Atomic Test"}
    tmp_storage.save_design("atomic-ok", data)

    path = tmp_storage._path("atomic-ok")
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == data


def test_save_design_roundtrip(tmp_storage: LocalStorage) -> None:
    """Data saved then loaded via load_design must be identical."""
    data = {"id": "rt-001", "name": "Round-Trip", "wing_span": 1200}
    tmp_storage.save_design("rt-001", data)
    loaded = tmp_storage.load_design("rt-001")
    assert loaded == data


def test_save_design_atomic_crash_leaves_original_intact(tmp_storage: LocalStorage) -> None:
    """If os.replace() raises mid-write the original file must be unchanged.

    This simulates a crash after the temp file has been written but before the
    atomic rename completes — the canonical scenario for #263.
    """
    original_data = {"id": "safe-001", "name": "Original"}
    tmp_storage.save_design("safe-001", original_data)

    # Confirm original is in place
    path = tmp_storage._path("safe-001")
    assert json.loads(path.read_text(encoding="utf-8")) == original_data

    # Simulate crash during the atomic rename
    with patch("os.replace", side_effect=OSError("Simulated crash")):
        with pytest.raises(OSError, match="Simulated crash"):
            tmp_storage.save_design("safe-001", {"id": "safe-001", "name": "Corrupted"})

    # Original file must still be intact
    assert json.loads(path.read_text(encoding="utf-8")) == original_data


def test_save_design_atomic_cleans_up_tempfile_on_failure(tmp_storage: LocalStorage, tmp_path: Path) -> None:
    """When os.replace() raises, the sibling .tmp_ file must be deleted."""
    storage = LocalStorage(base_path=str(tmp_path))

    with patch("os.replace", side_effect=OSError("Simulated crash")):
        with pytest.raises(OSError):
            storage.save_design("cleanup-test", {"id": "cleanup-test"})

    # No leftover .tmp_ files should remain in the storage directory
    leftover = list(tmp_path.glob(".tmp_*.json"))
    assert leftover == [], f"Temp files not cleaned up: {leftover}"


# ---------------------------------------------------------------------------
# Temp dir path consistency test (#262, #276)
# ---------------------------------------------------------------------------


def test_cleanup_and_export_use_same_tmp_dir() -> None:
    """DEFAULT_TMP_DIR in cleanup.py must equal EXPORT_TMP_DIR in export/package.py.

    This ensures the periodic cleanup daemon watches the same directory where
    export functions write their temp ZIP files (#262, #276).
    """
    from backend.cleanup import DEFAULT_TMP_DIR
    from backend.export.package import EXPORT_TMP_DIR

    assert DEFAULT_TMP_DIR == EXPORT_TMP_DIR, (
        f"cleanup.DEFAULT_TMP_DIR ({DEFAULT_TMP_DIR}) != "
        f"export.EXPORT_TMP_DIR ({EXPORT_TMP_DIR})"
    )
