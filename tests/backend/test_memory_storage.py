"""Tests for MemoryStorage — in-memory storage backend for cloud mode.

Covers thread safety, CRUD operations, introspection helpers, and the
FileNotFoundError contract that callers depend on.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from backend.storage import MemoryStorage


@pytest.fixture
def mem() -> MemoryStorage:
    """Fresh MemoryStorage instance for each test."""
    return MemoryStorage()


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(mem: MemoryStorage) -> None:
    """Data saved then loaded must be identical."""
    data = {"id": "d1", "name": "Test", "wing_span": 1000}
    mem.save_design("d1", data)
    loaded = mem.load_design("d1")
    assert loaded == data


def test_save_overwrites_existing(mem: MemoryStorage) -> None:
    """Saving with an existing id must replace the previous data."""
    mem.save_design("d1", {"id": "d1", "name": "Original"})
    mem.save_design("d1", {"id": "d1", "name": "Updated"})
    loaded = mem.load_design("d1")
    assert loaded["name"] == "Updated"


def test_load_not_found_raises(mem: MemoryStorage) -> None:
    """load_design must raise FileNotFoundError for unknown ids."""
    with pytest.raises(FileNotFoundError, match="Design not found: missing"):
        mem.load_design("missing")


def test_delete_removes_design(mem: MemoryStorage) -> None:
    """delete_design must remove the design so subsequent loads raise."""
    mem.save_design("d1", {"id": "d1", "name": "Del"})
    mem.delete_design("d1")
    with pytest.raises(FileNotFoundError):
        mem.load_design("d1")


def test_delete_not_found_raises(mem: MemoryStorage) -> None:
    """delete_design must raise FileNotFoundError for unknown ids."""
    with pytest.raises(FileNotFoundError, match="Design not found: ghost"):
        mem.delete_design("ghost")


# ---------------------------------------------------------------------------
# list_designs
# ---------------------------------------------------------------------------


def test_list_empty(mem: MemoryStorage) -> None:
    """list_designs returns an empty list when no designs are stored."""
    assert mem.list_designs() == []


def test_list_returns_summaries(mem: MemoryStorage) -> None:
    """list_designs returns id, name, and modified_at for each design."""
    mem.save_design("a", {"id": "a", "name": "Alpha"})
    mem.save_design("b", {"id": "b", "name": "Beta"})
    result = mem.list_designs()
    assert len(result) == 2
    ids = {r["id"] for r in result}
    assert ids == {"a", "b"}
    for r in result:
        assert "name" in r
        assert "modified_at" in r


def test_list_newest_first(mem: MemoryStorage) -> None:
    """list_designs returns designs in newest-first order.

    We patch the internal _timestamps dict directly to guarantee distinct
    timestamps without relying on wall-clock sub-millisecond timing, which
    can be flaky on fast CI machines.
    """
    from datetime import timedelta

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mem.save_design("old", {"id": "old", "name": "Old"})
    mem.save_design("new", {"id": "new", "name": "New"})
    # Force distinct timestamps to ensure deterministic sort order
    mem._timestamps["old"] = base
    mem._timestamps["new"] = base + timedelta(seconds=1)

    result = mem.list_designs()
    # "new" has the later timestamp, so it should appear first
    assert result[0]["id"] == "new"
    assert result[1]["id"] == "old"


def test_list_after_delete(mem: MemoryStorage) -> None:
    """Deleted designs must not appear in list_designs."""
    mem.save_design("d1", {"id": "d1", "name": "Keep"})
    mem.save_design("d2", {"id": "d2", "name": "Delete"})
    mem.delete_design("d2")
    result = mem.list_designs()
    assert len(result) == 1
    assert result[0]["id"] == "d1"


# ---------------------------------------------------------------------------
# Deep copy isolation
# ---------------------------------------------------------------------------


def test_stored_data_is_isolated(mem: MemoryStorage) -> None:
    """Mutating the original dict after save must not affect the stored copy."""
    data = {"id": "iso", "name": "Original"}
    mem.save_design("iso", data)
    data["name"] = "Mutated"  # mutate original
    loaded = mem.load_design("iso")
    assert loaded["name"] == "Original"


def test_loaded_data_is_isolated(mem: MemoryStorage) -> None:
    """Mutating the returned dict must not affect the stored copy."""
    mem.save_design("iso2", {"id": "iso2", "name": "Stored"})
    loaded = mem.load_design("iso2")
    loaded["name"] = "Modified"
    loaded_again = mem.load_design("iso2")
    assert loaded_again["name"] == "Stored"


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def test_design_count(mem: MemoryStorage) -> None:
    """design_count must track additions and deletions."""
    assert mem.design_count() == 0
    mem.save_design("a", {"id": "a"})
    assert mem.design_count() == 1
    mem.save_design("b", {"id": "b"})
    assert mem.design_count() == 2
    mem.delete_design("a")
    assert mem.design_count() == 1


def test_approximate_size_bytes(mem: MemoryStorage) -> None:
    """approximate_size_bytes must be positive after adding a design."""
    assert mem.approximate_size_bytes() == 0
    mem.save_design("a", {"id": "a", "name": "Alpha", "wing_span": 1200})
    size = mem.approximate_size_bytes()
    assert size > 0


def test_approximate_size_decreases_on_delete(mem: MemoryStorage) -> None:
    """approximate_size_bytes must decrease when designs are deleted."""
    mem.save_design("a", {"id": "a", "name": "Alpha"})
    mem.save_design("b", {"id": "b", "name": "Beta"})
    size_before = mem.approximate_size_bytes()
    mem.delete_design("b")
    size_after = mem.approximate_size_bytes()
    assert size_after < size_before


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_concurrent_saves_are_safe(mem: MemoryStorage) -> None:
    """Concurrent saves from multiple threads must not raise or lose data."""
    n_threads = 20
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            mem.save_design(f"design-{i}", {"id": f"design-{i}", "value": i})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
    assert mem.design_count() == n_threads


def test_concurrent_mixed_operations(mem: MemoryStorage) -> None:
    """Mixed concurrent saves and reads must not raise."""
    # Pre-populate
    for i in range(5):
        mem.save_design(f"pre-{i}", {"id": f"pre-{i}", "name": f"Pre {i}"})

    errors: list[Exception] = []

    def writer(i: int) -> None:
        try:
            mem.save_design(f"new-{i}", {"id": f"new-{i}"})
        except Exception as exc:
            errors.append(exc)

    def reader() -> None:
        try:
            mem.list_designs()
        except Exception as exc:
            errors.append(exc)

    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
