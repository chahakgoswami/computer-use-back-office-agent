"""Mock portal that routes URL requests to DOM page factories."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

from .dom import DOMDocument
from .pages import (
    build_confirmation_page,
    build_dashboard_page,
    build_error_page,
    build_form_page,
    build_login_page,
    build_records_page,
    build_upload_page,
)

# ---------------------------------------------------------------------------
# Portal response wrapper
# ---------------------------------------------------------------------------

class PortalResponse:
    """Encapsulates the result of a mock HTTP-style portal request."""

    def __init__(
        self,
        status: int,
        document: DOMDocument,
        redirect: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.status = status
        self.document = document
        self.redirect = redirect
        self.meta: Dict[str, Any] = meta or {}

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def __repr__(self) -> str:
        return (
            f"PortalResponse(status={self.status}, "
            f"title={self.document.title!r}, redirect={self.redirect!r})"
        )


# ---------------------------------------------------------------------------
# MockPortal
# ---------------------------------------------------------------------------

class MockPortal:
    """
    In-memory simulation of a legacy web portal.

    Tracks session state (logged-in user, submitted records, uploaded files)
    and responds to GET / POST actions with PortalResponse objects that
    contain fully-constructed DOMDocument trees.
    """

    # Hardcoded credential store (mock)
    _USERS: Dict[str, str] = {
        "admin": "secret",
        "operator": "pass123",
    }

    def __init__(self) -> None:
        self._session: Dict[str, Any] = {}
        self._records: list = []           # submitted form records
        self._uploads: list = []           # uploaded file metadata
        self._txn_counter: int = 0

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        return bool(self._session.get("username"))

    @property
    def current_user(self) -> Optional[str]:
        return self._session.get("username")

    def _require_auth(self) -> Optional[PortalResponse]:
        """Return a redirect response if the user is not logged in."""
        if not self.is_authenticated:
            return PortalResponse(
                status=302,
                document=build_login_page(),
                redirect="/login",
                meta={"reason": "unauthenticated"},
            )
        return None

    def _next_txn(self) -> str:
        self._txn_counter += 1
        return f"TXN-{self._txn_counter:05d}"

    # ------------------------------------------------------------------
    # GET requests
    # ------------------------------------------------------------------

    def get(self, path: str) -> PortalResponse:
        """Simulate a GET request to *path*."""
        path = path.rstrip("/") or "/"

        if path in ("/", "/login"):
            return PortalResponse(200, build_login_page())

        guard = self._require_auth()
        if guard:
            return guard

        routes = {
            "/dashboard": lambda: PortalResponse(
                200,
                build_dashboard_page(self.current_user),
            ),
            "/form": lambda: PortalResponse(200, build_form_page()),
            "/upload": lambda: PortalResponse(200, build_upload_page()),
            "/records": lambda: PortalResponse(
                200, build_records_page(self._records or None)
            ),
            "/logout": self._handle_logout,
        }
        handler = routes.get(path)
        if handler:
            return handler()
        return PortalResponse(404, build_error_page("Page not found.", 404))

    # ------------------------------------------------------------------
    # POST requests
    # ------------------------------------------------------------------

    def post(self, path: str, data: Dict[str, Any]) -> PortalResponse:
        """Simulate a POST request to *path* with form *data*."""
        path = path.rstrip("/") or "/"

        if path == "/login":
            return self._handle_login(data)

        guard = self._require_auth()
        if guard:
            return guard

        if path == "/form/submit":
            return self._handle_form_submit(data)
        if path == "/upload/submit":
            return self._handle_upload_submit(data)

        return PortalResponse(404, build_error_page("Endpoint not found.", 404))

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    def _handle_login(self, data: Dict[str, Any]) -> PortalResponse:
        username = (data.get("username") or "").strip()
        password = data.get("password", "")
        expected = self._USERS.get(username)
        if expected and expected == password:
            self._session = {"username": username}
            return PortalResponse(
                status=302,
                document=build_dashboard_page(username),
                redirect="/dashboard",
                meta={"username": username},
            )
        return PortalResponse(
            status=401,
            document=build_error_page("Invalid credentials.", 401),
            meta={"reason": "bad_credentials"},
        )

    def _handle_logout(self) -> PortalResponse:
        self._session = {}
        return PortalResponse(
            status=302,
            document=build_login_page(),
            redirect="/login",
            meta={"reason": "logged_out"},
        )

    def _handle_form_submit(self, data: Dict[str, Any]) -> PortalResponse:
        required = ["first_name", "last_name", "email"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return PortalResponse(
                status=422,
                document=build_error_page(
                    f"Missing required fields: {', '.join(missing)}", 422
                ),
                meta={"missing_fields": missing},
            )
        txn = self._next_txn()
        record = {
            "txn": txn,
            "submitted_by": self.current_user,
            **data,
        }
        self._records.append(record)
        return PortalResponse(
            status=200,
            document=build_confirmation_page(
                message="Form submitted successfully.",
                ref_id=txn,
            ),
            meta={"txn": txn, "record": record},
        )

    def _handle_upload_submit(self, data: Dict[str, Any]) -> PortalResponse:
        """Accept an upload payload (filename + content bytes or path)."""
        filename = data.get("upload_file") or data.get("filename", "")
        if not filename:
            return PortalResponse(
                status=422,
                document=build_error_page("No file specified.", 422),
                meta={"reason": "no_file"},
            )
        file_id = str(uuid.uuid4())[:8]
        upload_meta = {
            "file_id": file_id,
            "filename": filename,
            "category": data.get("file_category", ""),
            "uploaded_by": self.current_user,
            "size_bytes": data.get("size_bytes", 0),
        }
        self._uploads.append(upload_meta)
        return PortalResponse(
            status=200,
            document=build_confirmation_page(
                message=f"File '{filename}' uploaded successfully.",
                ref_id=file_id,
            ),
            meta={"file_id": file_id, "upload": upload_meta},
        )

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    def get_records(self) -> list:
        return list(self._records)

    def get_uploads(self) -> list:
        return list(self._uploads)

    def reset(self) -> None:
        """Reset all portal state (useful between tests)."""
        self._session = {}
        self._records = []
        self._uploads = []
        self._txn_counter = 0
