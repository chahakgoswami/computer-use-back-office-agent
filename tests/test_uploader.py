"""Tests for the Day-4 file-upload module."""

from __future__ import annotations

import os
import pytest

from agent.uploader import FileUploadHandler, UploadReceipt, BulkUploadReceipt
from agent.session_manager import SessionManager
from mock_browser.engine import MockBrowserEngine
from mock_browser.portal import MockPortal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures"
)


@pytest.fixture
def logged_in_engine():
    eng = MockBrowserEngine()
    eng.navigate("/login")
    eng.fill_field("username", "admin")
    eng.fill_field("password", "secret")
    eng.submit_form("login-form")
    return eng


@pytest.fixture
def handler(logged_in_engine):
    return FileUploadHandler(logged_in_engine, fixtures_dir=FIXTURES_DIR)


# ---------------------------------------------------------------------------
# UploadReceipt
# ---------------------------------------------------------------------------

class TestUploadReceipt:
    def test_as_dict_keys(self):
        r = UploadReceipt(
            local_path="fixtures/f.pdf",
            filename="f.pdf",
            category="report",
            size_bytes=512,
            status="ok",
            file_id="abc123",
        )
        d = r.as_dict()
        assert d["filename"] == "f.pdf"
        assert d["status"] == "ok"
        assert d["file_id"] == "abc123"

    def test_str_representation(self):
        r = UploadReceipt(
            local_path="a.pdf",
            filename="a.pdf",
            category="",
            size_bytes=100,
            status="ok",
            file_id="xyz",
        )
        assert "a.pdf" in str(r)
        assert "ok" in str(r)


# ---------------------------------------------------------------------------
# BulkUploadReceipt
# ---------------------------------------------------------------------------

class TestBulkUploadReceipt:
    def _make_bulk(self, statuses):
        from agent.uploader import BulkUploadReceipt, UploadReceipt
        bulk = BulkUploadReceipt()
        for s in statuses:
            bulk.receipts.append(
                UploadReceipt(
                    local_path="x", filename="x", category="",
                    size_bytes=0, status=s
                )
            )
        return bulk

    def test_all_ok(self):
        bulk = self._make_bulk(["ok", "ok", "ok"])
        assert bulk.status == "ok"
        assert bulk.success_count == 3
        assert bulk.error_count == 0

    def test_all_error(self):
        bulk = self._make_bulk(["error", "error"])
        assert bulk.status == "error"
        assert bulk.success_count == 0

    def test_partial(self):
        bulk = self._make_bulk(["ok", "error", "ok"])
        assert bulk.status == "partial"
        assert bulk.success_count == 2
        assert bulk.error_count == 1

    def test_as_dict(self):
        bulk = self._make_bulk(["ok"])
        d = bulk.as_dict()
        assert "receipts" in d
        assert d["success_count"] == 1


# ---------------------------------------------------------------------------
# FileUploadHandler – single file
# ---------------------------------------------------------------------------

class TestFileUploadHandlerSingle:
    def test_upload_existing_fixture(self, handler):
        receipt = handler.upload_file("sample_report.pdf", category="report")
        assert receipt.status == "ok"
        assert receipt.file_id is not None
        assert receipt.filename == "sample_report.pdf"
        assert receipt.size_bytes > 0
        assert receipt.category == "report"

    def test_upload_csv_fixture(self, handler):
        receipt = handler.upload_file("sample_invoice.csv", category="invoice")
        assert receipt.status == "ok"
        assert receipt.filename == "sample_invoice.csv"

    def test_upload_txt_fixture(self, handler):
        receipt = handler.upload_file("sample_contract.txt", category="contract")
        assert receipt.status == "ok"

    def test_upload_nonexistent_file_returns_error(self, handler):
        receipt = handler.upload_file("no_such_file.pdf", category="report")
        assert receipt.status == "error"
        assert receipt.error is not None
        assert receipt.file_id is None

    def test_upload_without_category(self, handler):
        receipt = handler.upload_file("sample_report.pdf")
        assert receipt.status == "ok"

    def test_upload_stores_in_portal(self, handler):
        initial = len(handler._engine.portal.get_uploads())
        handler.upload_file("sample_report.pdf", category="report")
        assert len(handler._engine.portal.get_uploads()) == initial + 1

    def test_upload_absolute_path(self, handler):
        abs_path = os.path.join(FIXTURES_DIR, "sample_report.pdf")
        receipt = handler.upload_file(abs_path, category="report")
        assert receipt.status == "ok"


# ---------------------------------------------------------------------------
# FileUploadHandler – bulk upload
# ---------------------------------------------------------------------------

class TestFileUploadHandlerBulk:
    def test_bulk_all_succeed(self, handler):
        files = [
            {"path": "sample_report.pdf", "category": "report"},
            {"path": "sample_invoice.csv", "category": "invoice"},
            {"path": "sample_contract.txt", "category": "contract"},
        ]
        bulk = handler.upload_files(files)
        assert bulk.status == "ok"
        assert bulk.success_count == 3
        assert bulk.error_count == 0
        assert bulk.finished_at is not None

    def test_bulk_partial_failure(self, handler):
        files = [
            {"path": "sample_report.pdf", "category": "report"},
            {"path": "missing_file.pdf", "category": "report"},
        ]
        bulk = handler.upload_files(files)
        assert bulk.status == "partial"
        assert bulk.success_count == 1
        assert bulk.error_count == 1

    def test_bulk_all_fail(self, handler):
        files = [
            {"path": "nope1.pdf"},
            {"path": "nope2.csv"},
        ]
        bulk = handler.upload_files(files)
        assert bulk.status == "error"
        assert bulk.success_count == 0

    def test_bulk_accumulates_portal_uploads(self, handler):
        files = [
            {"path": "sample_report.pdf"},
            {"path": "sample_invoice.csv"},
        ]
        handler.upload_files(files)
        assert len(handler._engine.portal.get_uploads()) == 2

    def test_bulk_empty_list(self, handler):
        bulk = handler.upload_files([])
        assert bulk.status == "ok"   # zero errors
        assert bulk.success_count == 0


# ---------------------------------------------------------------------------
# Integration: upload through SessionManager
# ---------------------------------------------------------------------------

class TestUploaderIntegration:
    def test_login_then_upload(self):
        session = SessionManager()
        session.login("admin", "secret")
        handler = FileUploadHandler(session.engine, fixtures_dir=FIXTURES_DIR)
        receipt = handler.upload_file("sample_report.pdf", category="report")
        assert receipt.status == "ok"
        assert len(session.portal.get_uploads()) == 1

    def test_unauthenticated_upload_returns_error(self):
        eng = MockBrowserEngine()
        # Not logged in
        handler = FileUploadHandler(eng, fixtures_dir=FIXTURES_DIR)
        receipt = handler.upload_file("sample_report.pdf", category="report")
        assert receipt.status == "error"
