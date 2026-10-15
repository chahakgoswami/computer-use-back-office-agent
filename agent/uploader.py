"""File-upload module: reads local fixture files and posts them to the mock portal."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mock_browser.engine import MockBrowserEngine, NavigationError


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class UploadError(Exception):
    """Raised when a file upload fails."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class UploadReceipt:
    """Structured result of a single file upload."""
    local_path: str
    filename: str
    category: str
    size_bytes: int
    status: str                    # "ok" | "error"
    file_id: Optional[str] = None  # portal-assigned id on success
    error: Optional[str] = None
    uploaded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"UploadReceipt(file={self.filename!r}, status={self.status}, "
            f"file_id={self.file_id!r}, size={self.size_bytes}B)"
        )


@dataclass
class BulkUploadReceipt:
    """Aggregated result of uploading multiple files."""
    receipts: List[UploadReceipt] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.receipts if r.status == "ok")

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.receipts if r.status == "error")

    @property
    def status(self) -> str:
        if self.error_count == 0:
            return "ok"
        if self.success_count == 0:
            return "error"
        return "partial"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "receipts": [r.as_dict() for r in self.receipts],
        }

    def __str__(self) -> str:
        return (
            f"BulkUploadReceipt(total={len(self.receipts)}, "
            f"ok={self.success_count}, error={self.error_count})"
        )


# ---------------------------------------------------------------------------
# FileUploadHandler
# ---------------------------------------------------------------------------

class FileUploadHandler:
    """
    Reads local fixture files and posts them to the mock portal's upload endpoint.

    Parameters
    ----------
    engine : MockBrowserEngine
        Authenticated browser engine.
    upload_url : str
        Portal endpoint to POST uploads to. Defaults to ``"/upload/submit"``.
    fixtures_dir : str | None
        Base directory for resolving relative fixture paths.  Defaults to the
        ``fixtures/`` sub-directory next to this module's package root.
    """

    DEFAULT_UPLOAD_URL = "/upload/submit"

    def __init__(
        self,
        engine: MockBrowserEngine,
        upload_url: str = DEFAULT_UPLOAD_URL,
        fixtures_dir: Optional[str] = None,
    ) -> None:
        self._engine = engine
        self._upload_url = upload_url
        if fixtures_dir is None:
            # <project_root>/fixtures
            _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fixtures_dir = os.path.join(_here, "fixtures")
        self._fixtures_dir = fixtures_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_file(
        self,
        local_path: str,
        category: str = "",
    ) -> UploadReceipt:
        """
        Upload a single file to the mock portal.

        Parameters
        ----------
        local_path : str
            Path to the fixture file.  If relative it is resolved against
            ``fixtures_dir``.
        category : str
            Portal file category (e.g. ``"report"``, ``"invoice"``).

        Returns
        -------
        UploadReceipt
        """
        resolved = self._resolve_path(local_path)
        filename = os.path.basename(resolved)

        # Read the file to get its size (simulate real upload)
        try:
            with open(resolved, "rb") as fh:
                content = fh.read()
            size_bytes = len(content)
        except OSError as exc:
            return UploadReceipt(
                local_path=local_path,
                filename=filename,
                category=category,
                size_bytes=0,
                status="error",
                error=f"Cannot read file {resolved!r}: {exc}",
            )

        payload = {
            "upload_file": filename,
            "file_category": category,
            "size_bytes": size_bytes,
        }

        try:
            resp = self._engine.portal.post(self._upload_url, payload)
        except Exception as exc:  # noqa: BLE001
            return UploadReceipt(
                local_path=local_path,
                filename=filename,
                category=category,
                size_bytes=size_bytes,
                status="error",
                error=str(exc),
            )

        if resp.status == 200:
            return UploadReceipt(
                local_path=local_path,
                filename=filename,
                category=category,
                size_bytes=size_bytes,
                status="ok",
                file_id=resp.meta.get("file_id"),
            )
        return UploadReceipt(
            local_path=local_path,
            filename=filename,
            category=category,
            size_bytes=size_bytes,
            status="error",
            error=f"Portal returned HTTP {resp.status}: {resp.meta}",
        )

    def upload_files(
        self,
        files: List[Dict[str, str]],
    ) -> BulkUploadReceipt:
        """
        Upload multiple files.

        Parameters
        ----------
        files : list of dict
            Each dict should have ``"path"`` and optionally ``"category"``.

        Returns
        -------
        BulkUploadReceipt
        """
        bulk = BulkUploadReceipt()
        for spec in files:
            receipt = self.upload_file(
                local_path=spec["path"],
                category=spec.get("category", ""),
            )
            bulk.receipts.append(receipt)
        bulk.finished_at = datetime.now(timezone.utc).isoformat()
        return bulk

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self._fixtures_dir, path)
