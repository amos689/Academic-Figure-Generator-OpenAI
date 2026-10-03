"""Local filesystem storage service — replaces MinIO."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class LocalStorageService:
    """Local filesystem-based storage for uploads and generated figures."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        settings = get_settings()
        self.data_dir = Path(data_dir or settings.DATA_DIR).resolve()
        self.uploads_dir = self.data_dir / "uploads"
        self.figures_dir = self.data_dir / "figures"
        self.exports_dir = self.data_dir / "exports"

        # Ensure directories exist
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        path = Path(storage_path)
        if (
            not storage_path
            or path.is_absolute()
            or "\\" in storage_path
            or "\x00" in storage_path
            or ".." in path.parts
            or len(path.parts) < 2
            or path.parts[0] not in {"uploads", "figures", "exports"}
        ):
            raise ValueError("Invalid storage path")
        target = (self.data_dir / path).resolve()
        root = self.data_dir / path.parts[0]
        if not target.is_relative_to(root) or target == root:
            raise ValueError("Storage path escapes its resource directory")
        return target

    def _save(self, storage_path: str, data: bytes) -> str:
        target = self._resolve(storage_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = self._resolve(storage_path)
        # Publish a complete file atomically, including after interrupted generation.
        descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return Path(storage_path).as_posix()

    def save_upload(self, relative_path: str, data: bytes) -> str:
        """Save uploaded file bytes to uploads directory.

        Returns the relative path from data_dir.
        """
        return self._save(f"uploads/{relative_path}", data)

    def save_figure(self, relative_path: str, data: bytes) -> str:
        """Save generated figure bytes to figures directory.

        Returns the relative path from data_dir.
        """
        return self._save(f"figures/{relative_path}", data)

    def save_export(self, relative_path: str, data: bytes) -> str:
        return self._save(f"exports/{relative_path}", data)

    def get_file(self, storage_path: str) -> bytes:
        """Read file bytes from storage path (relative to data_dir)."""
        target = self._resolve(storage_path)
        if not target.exists():
            raise FileNotFoundError("Stored file not found")
        return target.read_bytes()

    def get_file_path(self, storage_path: str) -> Path:
        """Get absolute path for a storage path."""
        return self._resolve(storage_path)

    def delete_file(self, storage_path: str) -> None:
        """Delete a file from storage."""
        target = self._resolve(storage_path)
        if target.exists():
            target.unlink()

    def file_exists(self, storage_path: str) -> bool:
        """Check if a file exists in storage."""
        return self._resolve(storage_path).is_file()
