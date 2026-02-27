"""Tests for CHENG_MODE toggle — MemoryStorage, get_cheng_mode(), create_storage_backend(), and /api/info.

Covers:
- MemoryStorage CRUD correctness
- MemoryStorage isolation (deep-copy semantics)
- get_cheng_mode() with valid values, default, and unknown values
- create_storage_backend() factory for both modes
- /api/info endpoint response in local and cloud modes
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.storage import MemoryStorage, create_storage_backend, get_cheng_mode


# ---------------------------------------------------------------------------
# MemoryStorage — CRUD tests
# ---------------------------------------------------------------------------


class TestMemoryStorageCRUD:
    def test_save_and_load_roundtrip(self) -> None:
        """Data saved then loaded must be identical."""
        storage = MemoryStorage()
        data = {"id": "rt-001", "name": "Round-Trip", "wing_span": 1200}
        storage.save_design("rt-001", data)
        loaded = storage.load_design("rt-001")
        assert loaded == data

    def test_load_not_found_raises(self) -> None:
        """load_design raises FileNotFoundError for an unknown id."""
        storage = MemoryStorage()
        with pytest.raises(FileNotFoundError, match="Design not found: missing"):
            storage.load_design("missing")

    def test_delete_removes_design(self) -> None:
        """delete_design removes the entry; subsequent load raises FileNotFoundError."""
        storage = MemoryStorage()
        storage.save_design("del-001", {"id": "del-001", "name": "ToDelete"})
        storage.delete_design("del-001")
        with pytest.raises(FileNotFoundError):
            storage.load_design("del-001")

    def test_delete_not_found_raises(self) -> None:
        """delete_design raises FileNotFoundError for an unknown id."""
        storage = MemoryStorage()
        with pytest.raises(FileNotFoundError, match="Design not found: ghost"):
            storage.delete_design("ghost")

    def test_list_designs_empty(self) -> None:
        """list_designs returns an empty list when nothing is stored."""
        storage = MemoryStorage()
        assert storage.list_designs() == []

    def test_list_designs_returns_summaries(self) -> None:
        """list_designs includes id and name for each stored design."""
        storage = MemoryStorage()
        storage.save_design("a", {"id": "a", "name": "Alpha"})
        storage.save_design("b", {"id": "b", "name": "Beta"})
        results = storage.list_designs()
        assert len(results) == 2
        ids = {r["id"] for r in results}
        assert ids == {"a", "b"}
        for r in results:
            assert "modified_at" in r

    def test_list_designs_sorted_newest_first(self) -> None:
        """list_designs returns designs sorted by modified_at descending."""
        storage = MemoryStorage()
        # Insert a and b; b is saved last so it should appear first
        storage.save_design("a", {"id": "a", "name": "Alpha"})
        storage.save_design("b", {"id": "b", "name": "Beta"})
        results = storage.list_designs()
        # The last-saved design (b) should be first
        assert results[0]["id"] == "b"

    def test_save_design_empty_id_raises(self) -> None:
        """save_design raises ValueError for an empty design_id."""
        storage = MemoryStorage()
        with pytest.raises(ValueError, match="Invalid design id"):
            storage.save_design("", {"id": "", "name": "Bad"})

    def test_upsert_overwrites_existing(self) -> None:
        """Saving with an existing id overwrites the stored design."""
        storage = MemoryStorage()
        storage.save_design("upsert-01", {"id": "upsert-01", "name": "Original"})
        storage.save_design("upsert-01", {"id": "upsert-01", "name": "Updated"})
        loaded = storage.load_design("upsert-01")
        assert loaded["name"] == "Updated"


# ---------------------------------------------------------------------------
# MemoryStorage — isolation (deep-copy semantics)
# ---------------------------------------------------------------------------


class TestMemoryStorageIsolation:
    def test_mutating_saved_data_does_not_affect_store(self) -> None:
        """Callers cannot corrupt stored data by mutating the dict they passed in."""
        storage = MemoryStorage()
        data = {"id": "iso-01", "name": "Original"}
        storage.save_design("iso-01", data)

        # Mutate after save
        data["name"] = "Mutated"
        loaded = storage.load_design("iso-01")
        assert loaded["name"] == "Original"

    def test_mutating_loaded_data_does_not_affect_store(self) -> None:
        """Callers cannot corrupt stored data by mutating the dict they received."""
        storage = MemoryStorage()
        storage.save_design("iso-02", {"id": "iso-02", "name": "Original"})

        loaded = storage.load_design("iso-02")
        loaded["name"] = "Mutated"

        reloaded = storage.load_design("iso-02")
        assert reloaded["name"] == "Original"


# ---------------------------------------------------------------------------
# get_cheng_mode()
# ---------------------------------------------------------------------------


class TestGetChengMode:
    @pytest.mark.smoke
    def test_default_is_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without CHENG_MODE set the default is 'local'."""
        monkeypatch.delenv("CHENG_MODE", raising=False)
        assert get_cheng_mode() == "local"

    @pytest.mark.smoke
    def test_local_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHENG_MODE", "local")
        assert get_cheng_mode() == "local"

    @pytest.mark.smoke
    def test_cloud_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHENG_MODE", "cloud")
        assert get_cheng_mode() == "cloud"

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHENG_MODE parsing is case-insensitive."""
        monkeypatch.setenv("CHENG_MODE", "Cloud")
        assert get_cheng_mode() == "cloud"
        monkeypatch.setenv("CHENG_MODE", "LOCAL")
        assert get_cheng_mode() == "local"

    def test_unknown_value_falls_back_to_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unrecognised CHENG_MODE value falls back to 'local'."""
        monkeypatch.setenv("CHENG_MODE", "purple")
        assert get_cheng_mode() == "local"

    def test_whitespace_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Leading/trailing whitespace in the env var is stripped."""
        monkeypatch.setenv("CHENG_MODE", "  cloud  ")
        assert get_cheng_mode() == "cloud"


# ---------------------------------------------------------------------------
# create_storage_backend() factory
# ---------------------------------------------------------------------------


class TestCreateStorageBackend:
    @pytest.mark.smoke
    def test_local_mode_returns_local_storage(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """In local mode the factory returns a LocalStorage instance."""
        from backend.storage import LocalStorage

        monkeypatch.setenv("CHENG_MODE", "local")
        monkeypatch.setenv("CHENG_DATA_DIR", str(tmp_path))
        backend = create_storage_backend()
        assert isinstance(backend, LocalStorage)

    @pytest.mark.smoke
    def test_cloud_mode_returns_memory_storage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In cloud mode the factory returns a MemoryStorage instance."""
        monkeypatch.setenv("CHENG_MODE", "cloud")
        backend = create_storage_backend()
        assert isinstance(backend, MemoryStorage)

    def test_default_mode_returns_local_storage(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Without CHENG_MODE set the factory returns a LocalStorage instance."""
        from backend.storage import LocalStorage

        monkeypatch.delenv("CHENG_MODE", raising=False)
        monkeypatch.setenv("CHENG_DATA_DIR", str(tmp_path))
        backend = create_storage_backend()
        assert isinstance(backend, LocalStorage)


# ---------------------------------------------------------------------------
# /api/info endpoint
# ---------------------------------------------------------------------------


class TestInfoEndpoint:
    @pytest.fixture
    def client(self) -> TestClient:
        from backend.main import app

        return TestClient(app)

    @pytest.mark.smoke
    def test_info_local_mode(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET /api/info returns mode='local' when CHENG_MODE is unset or 'local'."""
        monkeypatch.delenv("CHENG_MODE", raising=False)
        resp = client.get("/api/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "local"
        assert "version" in data
        assert "storage" in data
        assert "LocalStorage" in data["storage"]

    def test_info_cloud_mode(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET /api/info returns mode='cloud' when CHENG_MODE=cloud."""
        monkeypatch.setenv("CHENG_MODE", "cloud")
        resp = client.get("/api/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "cloud"
        assert "MemoryStorage" in data["storage"]

    @pytest.mark.smoke
    def test_info_returns_version(self, client: TestClient) -> None:
        """GET /api/info always includes a version field."""
        resp = client.get("/api/info")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.1.0"
