"""Storage backend — Protocol + LocalStorage implementation.

LocalStorage reads/writes .cheng JSON files to a directory on the Docker volume.
The StorageBackend Protocol exists so that a CloudStorage implementation can be
added in 1.0 without modifying calling code.
"""

from __future__ import annotations

import json
import os
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
        """Write design data as pretty-printed JSON."""
        path = self._path(design_id)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_design(self, design_id: str) -> dict:
        """Read and parse a saved design.  Raises FileNotFoundError if missing."""
        path = self._path(design_id)
        if not path.exists():
            raise FileNotFoundError(f"Design not found: {design_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_designs(self) -> list[dict]:
        """Return summaries of all saved designs, newest first.

        Uses os.stat() for timestamps and a partial JSON read to extract
        only 'id' and 'name' fields without parsing the entire file.
        """
        designs: list[dict] = []
        for p in sorted(
            self.base_path.glob("*.cheng"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        ):
            try:
                stat = os.stat(p)
                # Read only the first 1 KB to extract id/name without full parse
                with open(p, "r", encoding="utf-8") as f:
                    head = f.read(1024)
                data = json.loads(head if head.rstrip().endswith("}") else head + "}")
            except (json.JSONDecodeError, OSError, ValueError):
                # Fallback: full parse for files where partial read fails
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    stat = os.stat(p)
                except (json.JSONDecodeError, OSError):
                    continue  # skip corrupt files
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
