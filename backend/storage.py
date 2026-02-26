"""Storage backend — Protocol + LocalStorage + MemoryStorage implementations.

LocalStorage reads/writes .cheng JSON files to a directory on the Docker volume.
MemoryStorage is an in-memory backend for cloud mode (CHENG_MODE=cloud) where
the backend is stateless — no file I/O occurs.

The StorageBackend Protocol exists so that implementations can be swapped
without modifying calling code.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """Protocol defining the storage interface."""

    def save_design(self, design_id: str, data: dict) -> None: ...
    def load_design(self, design_id: str) -> dict: ...
    def list_designs(self) -> list[dict]: ...
    def delete_design(self, design_id: str) -> None: ...


class LocalStorage:
    """Reads/writes .cheng JSON files to a directory on the Docker volume."""

    def __init__(self, base_path: str = "/data/designs") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _safe_id(self, design_id: str) -> str:
        """Sanitize design_id to prevent path traversal attacks."""
        # Strip any directory components — only the final name is used
        safe = Path(design_id).name
        if not safe or safe in (".", ".."):
            raise ValueError(f"Invalid design id: {design_id!r}")
        return safe

    def _path(self, design_id: str) -> Path:
        """Return the filesystem path for a design, with traversal prevention."""
        safe_id = self._safe_id(design_id)
        return self.base_path / f"{safe_id}.cheng"

    def save_design(self, design_id: str, data: dict) -> None:
        """Write design data as pretty-printed JSON using an atomic write.

        Writes to a sibling temp file first, then uses os.replace() to
        atomically swap it into place.  This prevents a crash mid-write from
        leaving a truncated / corrupt JSON file (#263).

        os.replace() is atomic on POSIX (rename syscall) and best-effort on
        Windows (no rename-over-open-file guarantee, but still far safer than
        a direct write).
        """
        target = self._path(design_id)
        data_str = json.dumps(data, indent=2)
        tmp_fd, tmp_path_str = tempfile.mkstemp(
            dir=target.parent, prefix=".tmp_", suffix=".json"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(data_str)
            os.replace(tmp_path_str, target)
        except Exception:
            try:
                os.unlink(tmp_path_str)
            except OSError:
                pass
            raise

    def load_design(self, design_id: str) -> dict:
        """Read and parse a saved design.  Raises FileNotFoundError if missing."""
        path = self._path(design_id)
        if not path.exists():
            raise FileNotFoundError(f"Design not found: {design_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_designs(self) -> list[dict]:
        """Return summaries of all saved designs, newest first.

        Reads each .cheng file fully and extracts 'id' and 'name' fields.
        The files are local JSON on disk — full reads are fast and reliable.
        """
        designs: list[dict] = []
        for p in sorted(
            self.base_path.glob("*.cheng"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                stat = os.stat(p)
            except (json.JSONDecodeError, OSError):
                continue  # skip corrupt or unreadable files
            designs.append(
                {
                    "id": data.get("id", p.stem),
                    "name": data.get("name", "Untitled"),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
        return designs

    def delete_design(self, design_id: str) -> None:
        """Delete a saved design file.  Raises FileNotFoundError if missing."""
        path = self._path(design_id)
        if not path.exists():
            raise FileNotFoundError(f"Design not found: {design_id}")
        path.unlink()


class MemoryStorage:
    """In-memory storage backend for cloud mode (CHENG_MODE=cloud).

    Stores designs in a thread-safe dict keyed by design_id.
    No file I/O occurs — all data is lost on process restart.
    This is intentional: in cloud mode the browser (IndexedDB) is the
    canonical persistence layer; the backend is a pure stateless function.

    Capacity: practically unlimited (RAM-bound) per Cloud Run instance.
    Thread safety: all mutations are protected by a reentrant lock so that
    concurrent FastAPI handler threads cannot corrupt the dict.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._timestamps: dict[str, datetime] = {}
        self._lock = threading.RLock()

    def save_design(self, design_id: str, data: dict) -> None:
        """Store a deep copy of *data* under *design_id*.

        Deep-copying prevents accidental mutation of stored data via the
        original dict reference.
        """
        import copy

        with self._lock:
            self._store[design_id] = copy.deepcopy(data)
            self._timestamps[design_id] = datetime.now(tz=timezone.utc)

    def load_design(self, design_id: str) -> dict:
        """Return a deep copy of the stored design.  Raises FileNotFoundError if missing."""
        import copy

        with self._lock:
            if design_id not in self._store:
                raise FileNotFoundError(f"Design not found: {design_id}")
            return copy.deepcopy(self._store[design_id])

    def list_designs(self) -> list[dict]:
        """Return summaries of all stored designs, newest first."""
        with self._lock:
            entries = []
            for design_id, data in self._store.items():
                ts = self._timestamps.get(design_id, datetime.now(tz=timezone.utc))
                entries.append(
                    {
                        "id": data.get("id", design_id),
                        "name": data.get("name", "Untitled"),
                        "modified_at": ts.isoformat(),
                    }
                )
            # Sort newest first by timestamp
            entries.sort(
                key=lambda e: self._timestamps.get(e["id"], datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True,
            )
            return entries

    def delete_design(self, design_id: str) -> None:
        """Remove a design from memory.  Raises FileNotFoundError if missing."""
        with self._lock:
            if design_id not in self._store:
                raise FileNotFoundError(f"Design not found: {design_id}")
            del self._store[design_id]
            self._timestamps.pop(design_id, None)

    # ------------------------------------------------------------------
    # Introspection helpers (not part of the StorageBackend Protocol)
    # ------------------------------------------------------------------

    def design_count(self) -> int:
        """Return the number of designs currently in memory."""
        with self._lock:
            return len(self._store)

    def approximate_size_bytes(self) -> int:
        """Return approximate total byte size of all stored designs (JSON-serialised)."""
        with self._lock:
            total = 0
            for data in self._store.values():
                try:
                    total += len(json.dumps(data).encode("utf-8"))
                except (TypeError, ValueError):
                    pass
            return total
