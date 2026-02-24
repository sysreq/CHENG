"""Tests for the storage backend layer (LocalStorage).

Covers edge cases like path traversal, missing files, corrupted JSON,
and file permission errors.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def test_save_design_handles_io_error(tmp_storage: LocalStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    """save_design should bubble up OS/IO errors like disk full or permissions."""
    def mock_write_text(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(Path, "write_text", mock_write_text)

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


def test_list_designs_handles_partial_read_failure(tmp_storage: LocalStorage) -> None:
    """list_designs should fallback to full parse if partial read fails (e.g. minified JSON)."""
    # Write a minified JSON where the first 1024 bytes doesn't form a valid object even with a closing brace
    # Actually, a partial read might just cut a string in half.
    # Let's create a JSON with a very long string at the beginning.
    long_string = "A" * 2000
    data = {"id": "partial-fail", "name": "Partial Fail", "long_data": long_string}
    tmp_storage.save_design("partial-fail", data)

    designs = tmp_storage.list_designs()
    assert len(designs) == 1
    assert designs[0]["id"] == "partial-fail"
    assert designs[0]["name"] == "Partial Fail"


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

    # Mock the full parse read to raise OSError
    def mock_read_text(*args, **kwargs):
        raise OSError("Permission denied")

    # We need to make the partial read fail so it falls back to full parse
    # Or just mock the builtin open for the partial read too
    import builtins
    original_open = builtins.open

    def mock_open(path, *args, **kwargs):
        if str(path).endswith("unreadable.cheng"):
            raise OSError("Permission denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", mock_open)
    monkeypatch.setattr(Path, "read_text", mock_read_text)

    designs = tmp_storage.list_designs()
    assert len(designs) == 0


def test_delete_design_not_found(tmp_storage: LocalStorage) -> None:
    """delete_design should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError, match="Design not found: missing-id"):
        tmp_storage.delete_design("missing-id")
