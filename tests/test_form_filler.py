"""Tests for the Day-3 form-fill module."""

from __future__ import annotations

import pytest

from agent.form_filler import (
    FieldSpec,
    FieldValidator,
    FormFiller,
    FormReceipt,
    TransientError,
    TransientErrorSimulator,
    ValidationError,
)
from agent.session_manager import SessionManager
from mock_browser.engine import MockBrowserEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _logged_in_engine() -> MockBrowserEngine:
    """Return an engine that is already authenticated and on /form."""
    eng = MockBrowserEngine()
    eng.navigate("/login")
    eng.fill_field("username", "admin")
    eng.fill_field("password", "secret")
    eng.submit_form("login-form")
    eng.navigate("/form")
    return eng


# ---------------------------------------------------------------------------
# FieldValidator
# ---------------------------------------------------------------------------

class TestFieldValidator:
    def setup_method(self):
        self.v = FieldValidator()

    # --- required ---
    def test_required_empty_string_fails(self):
        ok, msg = self.v.validate("name", "", "text", required=True)
        assert not ok
        assert "required" in msg

    def test_required_none_fails(self):
        ok, msg = self.v.validate("name", None, "text", required=True)
        assert not ok

    def test_required_false_checkbox_fails(self):
        ok, msg = self.v.validate("agree", False, "checkbox", required=True)
        assert not ok

    def test_optional_empty_passes(self):
        ok, _ = self.v.validate("notes", "", "text", required=False)
        assert ok

    # --- email ---
    def test_valid_email(self):
        ok, _ = self.v.validate("email", "alice@example.com", "email")
        assert ok

    def test_invalid_email_no_at(self):
        ok, msg = self.v.validate("email", "notanemail", "email")
        assert not ok
        assert "e-mail" in msg

    def test_invalid_email_no_domain(self):
        ok, msg = self.v.validate("email", "alice@", "email")
        assert not ok

    # --- date ---
    def test_valid_date(self):
        ok, _ = self.v.validate("dob", "1990-06-15", "date")
        assert ok

    def test_invalid_date_format(self):
        ok, msg = self.v.validate("dob", "15/06/1990", "date")
        assert not ok
        assert "YYYY-MM-DD" in msg

    def test_invalid_date_value(self):
        ok, msg = self.v.validate("dob", "1990-13-01", "date")
        assert not ok

    # --- checkbox ---
    def test_checkbox_true(self):
        ok, _ = self.v.validate("agree", True, "checkbox")
        assert ok

    def test_checkbox_non_bool_fails(self):
        ok, msg = self.v.validate("agree", 1, "checkbox")
        assert not ok
        assert "bool" in msg

    # --- select ---
    def test_select_non_empty(self):
        ok, _ = self.v.validate("dept", "eng", "select")
        assert ok

    def test_select_empty_fails(self):
        ok, msg = self.v.validate("dept", "", "select")
        assert not ok

    # --- text ---
    def test_text_string_passes(self):
        ok, _ = self.v.validate("fname", "Alice", "text")
        assert ok

    def test_text_non_string_fails(self):
        ok, msg = self.v.validate("fname", 123, "text")
        assert not ok


# ---------------------------------------------------------------------------
# TransientErrorSimulator
# ---------------------------------------------------------------------------

class TestTransientErrorSimulator:
    def test_zero_rate_never_raises(self):
        sim = TransientErrorSimulator(error_rate=0.0)
        for _ in range(100):
            sim.maybe_raise("field")

    def test_full_rate_always_raises(self):
        sim = TransientErrorSimulator(error_rate=1.0)
        with pytest.raises(TransientError):
            sim.maybe_raise("field")

    def test_seeded_deterministic(self):
        sim1 = TransientErrorSimulator(error_rate=0.5, seed=42)
        sim2 = TransientErrorSimulator(error_rate=0.5, seed=42)
        results1, results2 = [], []
        for _ in range(10):
            try:
                sim1.maybe_raise("f")
                results1.append(False)
            except TransientError:
                results1.append(True)
            try:
                sim2.maybe_raise("f")
                results2.append(False)
            except TransientError:
                results2.append(True)
        assert results1 == results2

    def test_rate_clamped_above_1(self):
        sim = TransientErrorSimulator(error_rate=5.0)
        # Should always raise
        with pytest.raises(TransientError):
            sim.maybe_raise("f")

    def test_rate_clamped_below_0(self):
        sim = TransientErrorSimulator(error_rate=-1.0)
        sim.maybe_raise("f")  # must not raise


# ---------------------------------------------------------------------------
# FormFiller – field filling
# ---------------------------------------------------------------------------

class TestFormFillerFields:
    def _filler(self, fields, *, submit=False, error_rate=0.0, max_retries=3):
        eng = _logged_in_engine()
        sim = TransientErrorSimulator(error_rate=error_rate, seed=0)
        return FormFiller(
            eng,
            form_id="data-form",
            fields=fields,
            submit=submit,
            max_retries=max_retries,
            retry_delay=0.0,
            error_simulator=sim,
        )

    # text
    def test_fill_text_field(self):
        filler = self._filler([FieldSpec("first_name", "Alice", "text", required=True)])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"
        assert receipt.fields[0].validated

    def test_fill_required_text_empty_fails(self):
        filler = self._filler([FieldSpec("first_name", "", "text", required=True)])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"
        assert receipt.status in ("error", "partial")

    # email
    def test_fill_valid_email(self):
        filler = self._filler([FieldSpec("email", "a@b.com", "email")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"

    def test_fill_invalid_email(self):
        filler = self._filler([FieldSpec("email", "badmail", "email")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"

    # date
    def test_fill_valid_date(self):
        filler = self._filler([FieldSpec("dob", "1990-06-15", "date")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"

    def test_fill_invalid_date(self):
        filler = self._filler([FieldSpec("dob", "not-a-date", "date")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"

    # select / dropdown
    def test_fill_select(self):
        filler = self._filler([FieldSpec("department", "eng", "select")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"

    def test_fill_select_invalid_option(self):
        filler = self._filler([FieldSpec("department", "xyz", "select")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"

    # checkbox
    def test_fill_checkbox_true(self):
        filler = self._filler([FieldSpec("agree_terms", True, "checkbox")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"

    def test_fill_checkbox_non_bool_fails_validation(self):
        filler = self._filler([FieldSpec("agree_terms", 1, "checkbox")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"
        assert receipt.fields[0].attempts == 0   # rejected by validator, no attempt

    # textarea
    def test_fill_textarea(self):
        filler = self._filler([FieldSpec("notes", "Some notes here.", "textarea")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"

    # nonexistent field
    def test_fill_nonexistent_field_errors(self):
        filler = self._filler([FieldSpec("ghost_field", "x", "text")])
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"

    # multiple fields
    def test_fill_multiple_fields(self):
        filler = self._filler([
            FieldSpec("first_name", "Alice", "text", required=True),
            FieldSpec("last_name", "Smith", "text", required=True),
            FieldSpec("email", "alice@example.com", "email", required=True),
        ])
        receipt = filler.fill_and_submit()
        assert all(f.status == "ok" for f in receipt.fields)
        assert receipt.status == "ok"
        assert receipt.filled_count == 3
        assert receipt.error_count == 0


# ---------------------------------------------------------------------------
# FormFiller – transient error retry
# ---------------------------------------------------------------------------

class TestFormFillerRetry:
    def test_transient_error_retried_and_succeeds(self):
        """With error_rate slightly above 0 and enough retries, field eventually fills."""
        eng = _logged_in_engine()
        # Use a deterministic simulator that raises on first attempt only
        call_count = {"n": 0}
        original_maybe_raise = None

        class OnceErrorSim(TransientErrorSimulator):
            def maybe_raise(self, field_name):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise TransientError("first attempt blip")

        sim = OnceErrorSim(error_rate=0.0)
        filler = FormFiller(
            eng, "data-form",
            [FieldSpec("first_name", "Bob", "text")],
            submit=False,
            max_retries=3,
            retry_delay=0.0,
            error_simulator=sim,
        )
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "ok"
        assert receipt.fields[0].attempts == 2

    def test_exhaust_retries_marks_error(self):
        """When all retries fail the field receipt is 'error'."""
        eng = _logged_in_engine()
        sim = TransientErrorSimulator(error_rate=1.0)  # always fail
        filler = FormFiller(
            eng, "data-form",
            [FieldSpec("first_name", "Alice", "text")],
            submit=False,
            max_retries=3,
            retry_delay=0.0,
            error_simulator=sim,
        )
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].status == "error"
        assert receipt.fields[0].attempts == 3
        assert "3 attempts" in receipt.fields[0].error

    def test_max_retries_one_no_second_chance(self):
        eng = _logged_in_engine()
        sim = TransientErrorSimulator(error_rate=1.0)
        filler = FormFiller(
            eng, "data-form",
            [FieldSpec("first_name", "X", "text")],
            submit=False,
            max_retries=1,
            retry_delay=0.0,
            error_simulator=sim,
        )
        receipt = filler.fill_and_submit()
        assert receipt.fields[0].attempts == 1
        assert receipt.fields[0].status == "error"


# ---------------------------------------------------------------------------
# FormFiller – full submit flow
# ---------------------------------------------------------------------------

class TestFormFillerSubmit:
    def _full_fill_and_submit(self, extra_fields=None):
        eng = _logged_in_engine()
        fields = [
            FieldSpec("first_name", "Alice", "text", required=True),
            FieldSpec("last_name", "Smith", "text", required=True),
            FieldSpec("email", "alice@example.com", "email", required=True),
            FieldSpec("department", "eng", "select"),
            FieldSpec("agree_terms", True, "checkbox"),
        ]
        if extra_fields:
            fields.extend(extra_fields)
        filler = FormFiller(eng, "data-form", fields, submit=True, retry_delay=0.0)
        return filler.fill_and_submit()

    def test_successful_full_submit(self):
        receipt = self._full_fill_and_submit()
        assert receipt.status == "ok"
        assert receipt.submission_status == 200
        assert receipt.submission_ref is not None
        assert receipt.submission_ref.startswith("TXN-")

    def test_receipt_has_all_fields(self):
        receipt = self._full_fill_and_submit()
        names = {f.field_name for f in receipt.fields}
        assert "first_name" in names
        assert "agree_terms" in names

    def test_partial_status_when_some_fields_error(self):
        eng = _logged_in_engine()
        filler = FormFiller(eng, "data-form", [
            FieldSpec("first_name", "Alice", "text", required=True),
            FieldSpec("email", "notvalid", "email"),   # will fail validation
        ], submit=False, retry_delay=0.0)
        receipt = filler.fill_and_submit()
        assert receipt.status in ("partial", "error")
        assert receipt.error_count >= 1

    def test_no_submit_when_field_errors(self):
        """Form should NOT be submitted when there are field errors (submit=True)."""
        eng = _logged_in_engine()
        filler = FormFiller(eng, "data-form", [
            FieldSpec("email", "bad", "email"),
        ], submit=True, retry_delay=0.0)
        receipt = filler.fill_and_submit()
        assert receipt.submission_status is None   # never submitted

    def test_receipt_as_dict(self):
        receipt = self._full_fill_and_submit()
        d = receipt.as_dict()
        assert d["form_id"] == "data-form"
        assert isinstance(d["fields"], list)
        assert d["filled_count"] == 5
        assert "started_at" in d
        assert "finished_at" in d

    def test_receipt_str(self):
        receipt = self._full_fill_and_submit()
        s = str(receipt)
        assert "data-form" in s
        assert "ok" in s


# ---------------------------------------------------------------------------
# Integration: FormFiller through SessionManager
# ---------------------------------------------------------------------------

class TestFormFillerIntegration:
    def test_login_then_fill_form(self):
        session = SessionManager()
        session.login("admin", "secret")
        session.navigate("/form")

        filler = FormFiller(
            session.engine,
            form_id="data-form",
            fields=[
                FieldSpec("first_name", "Charlie", "text", required=True),
                FieldSpec("last_name", "Brown", "text", required=True),
                FieldSpec("email", "charlie@example.com", "email", required=True),
                FieldSpec("department", "fin", "select"),
                FieldSpec("agree_terms", True, "checkbox"),
                FieldSpec("dob", "1985-03-22", "date"),
            ],
            submit=True,
            retry_delay=0.0,
        )
        receipt = filler.fill_and_submit()
        assert receipt.status == "ok"
        assert receipt.submission_status == 200
        # Portal should have one record
        records = session.portal.get_records()
        assert len(records) == 1
        assert records[0]["first_name"] == "Charlie"

    def test_multiple_form_submissions_accumulate(self):
        session = SessionManager()
        session.login("admin", "secret")

        for i in range(3):
            session.navigate("/form")
            filler = FormFiller(
                session.engine,
                form_id="data-form",
                fields=[
                    FieldSpec("first_name", f"User{i}", "text", required=True),
                    FieldSpec("last_name", "Test", "text", required=True),
                    FieldSpec("email", f"user{i}@test.com", "email", required=True),
                ],
                submit=True,
                retry_delay=0.0,
            )
            receipt = filler.fill_and_submit()
            assert receipt.status == "ok"

        assert len(session.portal.get_records()) == 3
