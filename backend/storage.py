"""Storage backend — Protocol + LocalStorage + MemoryStorage implementations.

LocalStorage reads/writes .cheng JSON files to a directory on the Docker volume.
MemoryStorage keeps all designs in an in-memory dict (for Cloud Run / stateless mode).

The StorageBackend Protocol exists so that implementations can be swapped without
modifying calling code.  Use ``create_storage_backend()`` to obtain the correct
implementation for the current ``CHENG_MODE`` environment variable.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol


# ---------------------------------------------------------------------------
# CHENG_MODE helpers
# ---------------------------------------------------------------------------

ChengMode = Literal["local", "cloud"]
_VALID_MODES: frozenset[str] = frozenset({"local", "cloud"})


def get_cheng_mode() -> ChengMode:
    """Return the current CHENG_MODE value, defaulting to ``'local'``.

    Reads the ``CHENG_MODE`` environment variable.  Unrecognised values fall
    back to ``'local'`` with a warning so that a misconfigured deployment
    never silently breaks.

    Returns
    -------
    Literal["local", "cloud"]
        The validated mode string.
    """
    import logging

    raw = os.environ.get("CHENG_MODE", "local").strip().lower()
    if raw not in _VALID_MODES:
        logging.getLogger("cheng").warning(
            "Unknown CHENG_MODE=%r — falling back to 'local'. "
            "Valid values are: %s",
            raw,
            ", ".join(sorted(_VALID_MODES)),
        )
        return "local"
    return raw  # type: ignore[return-value]


def create_storage_backend() -> "LocalStorage | MemoryStorage":
    """Factory: return the appropriate StorageBackend for the current CHENG_MODE.

    - ``local``  → :class:`LocalStorage` (file-based, persists across restarts)
    - ``cloud``  → :class:`MemoryStorage` (in-memory, stateless, no file I/O)

    The storage path for ``LocalStorage`` is read from the ``CHENG_DATA_DIR``
    environment variable (default ``/data/designs``).
    """
    mode = get_cheng_mode()
    if mode == "cloud":
        return MemoryStorage()
    return LocalStorage(
        base_path=os.environ.get("CHENG_DATA_DIR", "/data/designs")
    )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class StorageBackend(Protocol):
    """Protocol defining the storage interface."""

    def save_design(self, design_id: str, data: dict) -> None: ...
    def load_design(self, design_id: str) -> dict: ...
    def list_designs(self) -> list[dict]: ...
    def delete_design(self, design_id: str) -> None: ...


# ---------------------------------------------------------------------------
# LocalStorage — file-based, for local Docker mode
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MemoryStorage — in-memory, for Cloud Run / stateless mode
# ---------------------------------------------------------------------------


class MemoryStorage:
    """Stores designs in an in-memory dict.

    Intended for Cloud Run deployments where the backend is stateless and all
    persistent design state lives in the browser (Zustand store + IndexedDB).
    Data is NOT preserved across process restarts.

    Thread safety: operations are protected by a simple dict copy strategy;
    for the expected single-process Cloud Run use-case this is sufficient.
    Each ``save_design`` / ``load_design`` call deep-copies data so that
    callers cannot mutate internal state via the returned reference.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._timestamps: dict[str, datetime] = {}

    def save_design(self, design_id: str, data: dict) -> None:
        """Store a deep copy of *data* keyed by *design_id*."""
        if not design_id:
            raise ValueError(f"Invalid design id: {design_id!r}")
        self._store[design_id] = copy.deepcopy(data)
        self._timestamps[design_id] = datetime.now(tz=timezone.utc)

    def load_design(self, design_id: str) -> dict:
        """Return a deep copy of the stored design.

        Raises
        ------
        FileNotFoundError
            If *design_id* has not been saved.
        """
        if design_id not in self._store:
            raise FileNotFoundError(f"Design not found: {design_id}")
        return copy.deepcopy(self._store[design_id])

    def list_designs(self) -> list[dict]:
        """Return summaries of all stored designs, newest first."""
        designs = []
        for design_id, data in self._store.items():
            ts = self._timestamps.get(design_id, datetime.now(tz=timezone.utc))
            designs.append(
                {
                    "id": data.get("id", design_id),
                    "name": data.get("name", "Untitled"),
                    "modified_at": ts.isoformat(),
                }
            )
        # Sort newest first
        designs.sort(key=lambda d: d["modified_at"], reverse=True)
        return designs

    def delete_design(self, design_id: str) -> None:
        """Remove the stored design.

        Raises
        ------
        FileNotFoundError
            If *design_id* has not been saved.
        """
        if design_id not in self._store:
            raise FileNotFoundError(f"Design not found: {design_id}")
        del self._store[design_id]
        self._timestamps.pop(design_id, None)
