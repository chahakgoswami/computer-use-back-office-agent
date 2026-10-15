"""Tests for the Day-4 data-extraction module."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from agent.extractor import DataExtractor, ExtractionResult
from agent.session_manager import SessionManager
from mock_browser.engine import MockBrowserEngine
from mock_browser.portal import MockPortal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_results(tmp_path):
    return str(tmp_path / "results")


@pytest.fixture
def logged_in_engine():
    eng = MockBrowserEngine()
    eng.navigate("/login")
    eng.fill_field("username", "admin")
    eng.fill_field("password", "secret")
    eng.submit_form("login-form")
    return eng


@pytest.fixture
def extractor(logged_in_engine, tmp_results):
    return DataExtractor(logged_in_engine, results_dir=tmp_results)


# ---------------------------------------------------------------------------
# ExtractionResult
# ---------------------------------------------------------------------------

class TestExtractionResult:
    def test_ok_when_no_error(self):
        r = ExtractionResult(url="/records", page_type="table", data=[])
        assert r.ok is True

    def test_not_ok_when_error_set(self):
        r = ExtractionResult(
            url="/records", page_type="table", data=[], error="fail"
        )
        assert r.ok is False

    def test_as_dict_keys(self):
        r = ExtractionResult(
            url="/records", page_type="table",
            data=[{"ID": "REC-001"}]
        )
        d = r.as_dict()
        assert d["url"] == "/records"
        assert d["page_type"] == "table"
        assert isinstance(d["data"], list)

    def test_str_representation(self):
        r = ExtractionResult(url="/records", page_type="table", data=[1, 2])
        s = str(r)
        assert "/records" in s
        assert "table" in s


# ---------------------------------------------------------------------------
# DataExtractor – table page
# ---------------------------------------------------------------------------

class TestExtractTablePage:
    def test_extract_records_page(self, extractor):
        result = extractor.extract_page("/records", save=False)
        assert result.ok
        assert result.page_type == "table"
        assert isinstance(result.data, list)
        assert len(result.data) == 3   # default mock records

    def test_records_have_expected_columns(self, extractor):
        result = extractor.extract_page("/records", save=False)
        for row in result.data:
            assert "ID" in row
            assert "Name" in row
            assert "Department" in row
            assert "Status" in row

    def test_records_values_correct(self, extractor):
        result = extractor.extract_page("/records", save=False)
        ids = [row["ID"] for row in result.data]
        assert "REC-001" in ids
        assert "REC-002" in ids
        assert "REC-003" in ids

    def test_submitted_records_appear_in_extraction(self, logged_in_engine, tmp_results):
        """Records submitted via the portal should be visible when scraped."""
        portal = logged_in_engine.portal
        portal.post("/form/submit", {
            "first_name": "Dana",
            "last_name": "Lee",
            "email": "dana@example.com",
        })
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        # Navigate to records so the page shows submitted records
        # The portal's records page uses stored records when available
        result = extractor.extract_page("/records", save=False)
        assert result.ok
        assert result.page_type == "table"
        # Submitted record should appear
        names = [row.get("Name", "") for row in result.data]
        assert any("Dana" in n for n in names)


# ---------------------------------------------------------------------------
# DataExtractor – confirmation page
# ---------------------------------------------------------------------------

class TestExtractConfirmationPage:
    def _submit_and_get_response(self, portal):
        return portal.post("/form/submit", {
            "first_name": "Eve",
            "last_name": "Carter",
            "email": "eve@example.com",
        })

    def test_extract_from_response_confirmation(self, logged_in_engine, tmp_results):
        portal = logged_in_engine.portal
        resp = self._submit_and_get_response(portal)
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        result = extractor.extract_from_response("/form/submit", resp, save=False)
        assert result.ok
        assert result.page_type == "confirmation"
        assert "message" in result.data
        assert "ref_id" in result.data

    def test_confirmation_message_content(self, logged_in_engine, tmp_results):
        portal = logged_in_engine.portal
        resp = self._submit_and_get_response(portal)
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        result = extractor.extract_from_response("/form/submit", resp, save=False)
        assert "successfully" in result.data["message"].lower()

    def test_confirmation_ref_id_extracted(self, logged_in_engine, tmp_results):
        portal = logged_in_engine.portal
        resp = self._submit_and_get_response(portal)
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        result = extractor.extract_from_response("/form/submit", resp, save=False)
        assert result.data["ref_id"].startswith("TXN-")

    def test_upload_confirmation_extracted(self, logged_in_engine, tmp_results):
        portal = logged_in_engine.portal
        resp = portal.post("/upload/submit", {
            "upload_file": "report.pdf",
            "file_category": "report",
            "size_bytes": 1024,
        })
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        result = extractor.extract_from_response("/upload/submit", resp, save=False)
        assert result.ok
        assert result.page_type == "confirmation"
        assert result.data["ref_id"]  # file_id is the ref


# ---------------------------------------------------------------------------
# DataExtractor – error handling
# ---------------------------------------------------------------------------

class TestExtractErrors:
    def test_404_page_returns_error_result(self, extractor):
        result = extractor.extract_page("/nonexistent", save=False)
        assert not result.ok
        assert result.error is not None

    def test_extract_from_bad_response(self, logged_in_engine, tmp_results):
        from mock_browser.pages import build_error_page
        from mock_browser.portal import PortalResponse
        resp = PortalResponse(
            status=422,
            document=build_error_page("bad", 422),
            meta={},
        )
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        result = extractor.extract_from_response("/form/submit", resp, save=False)
        assert not result.ok

    def test_unknown_page_type_returns_result_with_title(self, logged_in_engine, tmp_results):
        """Dashboard doesn't match table/confirmation – falls back to unknown."""
        extractor = DataExtractor(logged_in_engine, results_dir=tmp_results)
        result = extractor.extract_page("/dashboard", save=False)
        # Should not raise; page_type is 'unknown' but result is still returned
        assert result is not None
        assert result.page_type == "unknown"


# ---------------------------------------------------------------------------
# DataExtractor – file persistence
# ---------------------------------------------------------------------------

class TestExtractSave:
    def test_save_creates_file(self, extractor, tmp_results):
        result = extractor.extract_page("/records", save=True)
        assert result.saved_path is not None
        assert os.path.exists(result.saved_path)

    def test_saved_file_is_valid_json(self, extractor, tmp_results):
        result = extractor.extract_page("/records", save=True)
        with open(result.saved_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["page_type"] == "table"
        assert isinstance(data["data"], list)

    def test_save_false_no_file_created(self, extractor, tmp_results):
        result = extractor.extract_page("/records", save=False)
        assert result.saved_path is None
        # results dir may not even exist
        if os.path.exists(tmp_results):
            files = os.listdir(tmp_results)
            assert len(files) == 0

    def test_multiple_extractions_create_separate_files(self, extractor, tmp_results):
        extractor.extract_page("/records", save=True)
        extractor.extract_page("/records", save=True)
        files = os.listdir(tmp_results)
        assert len(files) == 2

    def test_results_dir_created_automatically(self, logged_in_engine, tmp_path):
        new_dir = str(tmp_path / "deep" / "results")
        extractor = DataExtractor(logged_in_engine, results_dir=new_dir)
        result = extractor.extract_page("/records", save=True)
        assert os.path.isdir(new_dir)
        assert result.saved_path is not None

    def test_saved_json_contains_url_and_timestamp(self, extractor, tmp_results):
        result = extractor.extract_page("/records", save=True)
        with open(result.saved_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["url"] == "/records"
        assert data["extracted_at"]


# ---------------------------------------------------------------------------
# Integration: extractor through SessionManager
# ---------------------------------------------------------------------------

class TestExtractorIntegration:
    def test_full_flow_submit_then_extract(self, tmp_results):
        """Submit a form then extract both confirmation and records pages."""
        session = SessionManager()
        session.login("admin", "secret")
        extractor = DataExtractor(session.engine, results_dir=tmp_results)

        # Submit a form record via the portal
        session.navigate("/form")
        session.fill_field("first_name", "Frank")
        session.fill_field("last_name", "Ocean")
        session.fill_field("email", "frank@example.com")
        resp = session.submit_form("data-form")

        # Extract confirmation from the already-loaded response
        conf_result = extractor.extract_from_response(
            "/form/submit", resp, save=True
        )
        assert conf_result.ok
        assert conf_result.page_type == "confirmation"
        assert conf_result.data["ref_id"].startswith("TXN-")

        # Extract the records table
        rec_result = extractor.extract_page("/records", save=True)
        assert rec_result.ok
        assert rec_result.page_type == "table"
        assert len(rec_result.data) == 1  # only Frank's record
        assert rec_result.data[0]["Name"] == "Frank Ocean"

        # Two JSON files saved
        saved_files = os.listdir(tmp_results)
        assert len(saved_files) == 2
