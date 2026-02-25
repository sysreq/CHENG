"""Storage backend — Protocol + LocalStorage implementation.

LocalStorage reads/writes .cheng JSON files to a directory on the Docker volume.
The StorageBackend Protocol exists so that a CloudStorage implementation can be
added in 1.0 without modifying calling code.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """Protocol defining the storage interface.  MVP implements LocalStorage only."""

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
