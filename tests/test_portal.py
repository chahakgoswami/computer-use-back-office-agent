"""Unit tests for MockPortal – simulated GET / POST routing."""

import pytest
from mock_browser.portal import MockPortal


@pytest.fixture
def portal():
    p = MockPortal()
    yield p
    p.reset()


@pytest.fixture
def logged_in_portal():
    p = MockPortal()
    p.post("/login", {"username": "admin", "password": "secret"})
    yield p
    p.reset()


class TestGetRoutes:
    def test_login_page_accessible_without_auth(self, portal):
        resp = portal.get("/login")
        assert resp.status == 200
        assert "Login" in resp.document.title

    def test_root_redirects_to_login(self, portal):
        resp = portal.get("/")
        assert resp.status == 200  # login page served

    def test_protected_route_redirects_when_unauthenticated(self, portal):
        resp = portal.get("/dashboard")
        assert resp.status == 302
        assert resp.redirect == "/login"

    def test_dashboard_after_login(self, logged_in_portal):
        resp = logged_in_portal.get("/dashboard")
        assert resp.status == 200
        assert "Dashboard" in resp.document.title

    def test_form_page(self, logged_in_portal):
        resp = logged_in_portal.get("/form")
        assert resp.status == 200
        form = resp.document.find("form", id="data-form")
        assert form is not None

    def test_upload_page(self, logged_in_portal):
        resp = logged_in_portal.get("/upload")
        assert resp.status == 200
        form = resp.document.find("form", id="upload-form")
        assert form is not None

    def test_records_page(self, logged_in_portal):
        resp = logged_in_portal.get("/records")
        assert resp.status == 200
        table = resp.document.find("table", id="records-table")
        assert table is not None

    def test_unknown_route_returns_404(self, logged_in_portal):
        resp = logged_in_portal.get("/nonexistent")
        assert resp.status == 404


class TestLogin:
    def test_valid_credentials(self, portal):
        resp = portal.post("/login",
                           {"username": "admin", "password": "secret"})
        assert resp.status == 302
        assert resp.redirect == "/dashboard"
        assert portal.is_authenticated

    def test_invalid_credentials(self, portal):
        resp = portal.post("/login",
                           {"username": "admin", "password": "wrong"})
        assert resp.status == 401
        assert not portal.is_authenticated

    def test_unknown_user(self, portal):
        resp = portal.post("/login",
                           {"username": "nobody", "password": "x"})
        assert resp.status == 401

    def test_logout(self, logged_in_portal):
        resp = logged_in_portal.get("/logout")
        assert resp.status == 302
        assert not logged_in_portal.is_authenticated


class TestFormSubmit:
    def test_valid_form_submission(self, logged_in_portal):
        data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "department": "eng",
            "agree_terms": True,
        }
        resp = logged_in_portal.post("/form/submit", data)
        assert resp.status == 200
        assert "Confirmation" in resp.document.title
        assert "txn" in resp.meta

    def test_missing_required_fields(self, logged_in_portal):
        resp = logged_in_portal.post("/form/submit", {"first_name": "Alice"})
        assert resp.status == 422
        assert "last_name" in resp.meta.get("missing_fields", [])

    def test_records_accumulate(self, logged_in_portal):
        for i in range(3):
            logged_in_portal.post("/form/submit", {
                "first_name": f"User{i}",
                "last_name": "Test",
                "email": f"u{i}@test.com",
            })
        assert len(logged_in_portal.get_records()) == 3


class TestUploadSubmit:
    def test_valid_upload(self, logged_in_portal):
        resp = logged_in_portal.post("/upload/submit", {
            "upload_file": "report.pdf",
            "file_category": "report",
            "size_bytes": 1024,
        })
        assert resp.status == 200
        assert "file_id" in resp.meta

    def test_missing_file(self, logged_in_portal):
        resp = logged_in_portal.post("/upload/submit", {})
        assert resp.status == 422

    def test_uploads_accumulate(self, logged_in_portal):
        for fname in ["a.pdf", "b.csv", "c.xlsx"]:
            logged_in_portal.post("/upload/submit",
                                   {"upload_file": fname})
        assert len(logged_in_portal.get_uploads()) == 3
