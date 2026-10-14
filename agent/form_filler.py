"""Form-fill module: validates and fills form fields with retry on transient errors."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from mock_browser.engine import MockBrowserEngine, NavigationError


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a field value fails validation."""


class TransientError(Exception):
    """Simulated transient portal error (network blip, timeout, etc.)."""


class FormFillError(Exception):
    """Raised when form filling fails after all retries."""


# ---------------------------------------------------------------------------
# Field descriptors
# ---------------------------------------------------------------------------

@dataclass
class FieldReceipt:
    """Result record for a single field fill attempt."""
    field_name: str
    field_type: str
    value: Any
    status: str          # "ok" | "error" | "skipped"
    attempts: int = 1
    error: Optional[str] = None
    validated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FormReceipt:
    """Structured receipt produced after completing (or failing) a form."""
    form_id: str
    url: str
    started_at: str
    finished_at: str
    status: str                          # "ok" | "partial" | "error"
    fields: List[FieldReceipt] = field(default_factory=list)
    submission_status: Optional[int] = None   # HTTP status from portal
    submission_ref: Optional[str] = None      # txn id / confirmation ref
    error: Optional[str] = None

    # summary helpers
    @property
    def filled_count(self) -> int:
        return sum(1 for f in self.fields if f.status == "ok")

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.fields if f.status == "error")

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["filled_count"] = self.filled_count
        d["error_count"] = self.error_count
        return d

    def __str__(self) -> str:
        return (
            f"FormReceipt(form={self.form_id!r}, status={self.status}, "
            f"fields={len(self.fields)}, filled={self.filled_count}, "
            f"errors={self.error_count})"
        )


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class FieldValidator:
    """
    Validates field values before submission.

    Rules are keyed on field type:
      text     – non-empty string
      email    – basic e-mail pattern
      date     – YYYY-MM-DD format
      select   – non-empty string
      checkbox – bool
      textarea – any string
    """

    EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def validate(self, name: str, value: Any, field_type: str,
                 required: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate *value* for *field_type*.

        Returns (True, None) on success or (False, reason) on failure.
        """
        if required and (value is None or value == "" or value is False):
            return False, f"{name!r} is required but empty."

        if value is None or value == "":
            return True, None   # optional and empty – fine

        if field_type == "email":
            if not self.EMAIL_RE.match(str(value)):
                return False, f"{name!r}: {value!r} is not a valid e-mail address."

        elif field_type == "date":
            if not self.DATE_RE.match(str(value)):
                return False, (
                    f"{name!r}: {value!r} must be YYYY-MM-DD format."
                )
            # Also check it parses as a real date
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError as exc:
                return False, f"{name!r}: {exc}"

        elif field_type == "checkbox":
            if not isinstance(value, bool):
                return False, f"{name!r}: checkbox value must be bool, got {type(value).__name__}."

        elif field_type == "select":
            if not isinstance(value, str) or not value:
                return False, f"{name!r}: select value must be a non-empty string."

        elif field_type in ("text", "password", "textarea"):
            if not isinstance(value, str):
                return False, f"{name!r}: expected str, got {type(value).__name__}."

        return True, None


# ---------------------------------------------------------------------------
# Transient error simulator
# ---------------------------------------------------------------------------

class TransientErrorSimulator:
    """
    Injects random transient errors to simulate flaky portal behaviour.

    Parameters
    ----------
    error_rate : float
        Probability of injecting an error on any given fill attempt.
    seed : int | None
        Optional RNG seed for deterministic tests.
    """

    def __init__(self, error_rate: float = 0.0, seed: Optional[int] = None) -> None:
        self._rate = max(0.0, min(1.0, error_rate))
        self._rng = random.Random(seed)

    def maybe_raise(self, field_name: str) -> None:
        """Raise TransientError with probability ``error_rate``."""
        if self._rng.random() < self._rate:
            raise TransientError(
                f"Simulated transient error while filling {field_name!r}."
            )


# ---------------------------------------------------------------------------
# FormFiller
# ---------------------------------------------------------------------------

@dataclass
class FieldSpec:
    """
    Specification for a single form field to be filled.

    Attributes
    ----------
    name : str
        The HTML ``name`` attribute of the field.
    value : Any
        The value to fill / select / check.
    field_type : str
        One of: ``text``, ``email``, ``date``, ``select``, ``checkbox``,
        ``textarea``, ``password``.  Defaults to ``text``.
    required : bool
        If True the validator enforces a non-empty value.
    """
    name: str
    value: Any
    field_type: str = "text"
    required: bool = False


class FormFiller:
    """
    High-level form-fill controller.

    Usage
    -----
    .. code-block:: python

        filler = FormFiller(engine, form_id="data-form",
                            fields=[FieldSpec("first_name", "Alice", required=True),
                                    FieldSpec("email", "alice@x.com", field_type="email"),
                                    FieldSpec("department", "eng", field_type="select"),
                                    FieldSpec("agree_terms", True, field_type="checkbox")])
        receipt = filler.fill_and_submit()

    Parameters
    ----------
    engine : MockBrowserEngine
    form_id : str
        DOM id of the form to fill and submit.
    fields : list[FieldSpec]
        Ordered list of fields to fill.
    submit : bool
        If True (default), submit the form after filling.
    max_retries : int
        Maximum per-field retry attempts on transient errors.
    retry_delay : float
        Seconds to sleep between retries (use 0 for tests).
    validator : FieldValidator | None
        Custom validator; uses a default instance if not provided.
    error_simulator : TransientErrorSimulator | None
        Inject transient errors; defaults to zero-rate simulator.
    """

    def __init__(
        self,
        engine: MockBrowserEngine,
        form_id: str,
        fields: List[FieldSpec],
        *,
        submit: bool = True,
        max_retries: int = 3,
        retry_delay: float = 0.0,
        validator: Optional[FieldValidator] = None,
        error_simulator: Optional[TransientErrorSimulator] = None,
    ) -> None:
        self._engine = engine
        self._form_id = form_id
        self._fields = fields
        self._submit = submit
        self._max_retries = max(1, max_retries)
        self._retry_delay = retry_delay
        self._validator = validator or FieldValidator()
        self._sim = error_simulator or TransientErrorSimulator(error_rate=0.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fill_and_submit(self) -> FormReceipt:
        """
        Fill every field, optionally submit the form, and return a FormReceipt.
        """
        started_at = _now()
        field_receipts: List[FieldReceipt] = []
        any_error = False

        for spec in self._fields:
            receipt = self._fill_field_with_retry(spec)
            field_receipts.append(receipt)
            if receipt.status == "error":
                any_error = True

        submission_status: Optional[int] = None
        submission_ref: Optional[str] = None
        form_error: Optional[str] = None

        if self._submit and not any_error:
            try:
                resp = self._engine.submit_form(self._form_id)
                submission_status = resp.status
                submission_ref = (
                    resp.meta.get("txn")
                    or resp.meta.get("file_id")
                    or None
                )
                if resp.status >= 400:
                    form_error = (
                        f"Submission returned HTTP {resp.status}: "
                        f"{resp.meta}"
                    )
            except (NavigationError, Exception) as exc:
                form_error = str(exc)
                any_error = True

        finished_at = _now()
        overall = "ok"
        if any_error:
            overall = "error" if not field_receipts or all(
                f.status != "ok" for f in field_receipts
            ) else "partial"
        if form_error and overall == "ok":
            overall = "error"

        return FormReceipt(
            form_id=self._form_id,
            url=self._engine.current_url,
            started_at=started_at,
            finished_at=finished_at,
            status=overall,
            fields=field_receipts,
            submission_status=submission_status,
            submission_ref=submission_ref,
            error=form_error,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fill_field_with_retry(self, spec: FieldSpec) -> FieldReceipt:
        """Attempt to validate and fill a single field, retrying on transient errors."""
        # Validate first (no retries for validation failures)
        ok, reason = self._validator.validate(
            spec.name, spec.value, spec.field_type, required=spec.required
        )
        if not ok:
            return FieldReceipt(
                field_name=spec.name,
                field_type=spec.field_type,
                value=spec.value,
                status="error",
                attempts=0,
                error=reason,
                validated=False,
            )

        last_error: Optional[str] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                # May raise TransientError
                self._sim.maybe_raise(spec.name)
                self._apply_field(spec)
                return FieldReceipt(
                    field_name=spec.name,
                    field_type=spec.field_type,
                    value=spec.value,
                    status="ok",
                    attempts=attempt,
                    validated=True,
                )
            except TransientError as exc:
                last_error = str(exc)
                if attempt < self._max_retries and self._retry_delay > 0:
                    time.sleep(self._retry_delay)
            except (NavigationError, Exception) as exc:
                # Non-transient: fail immediately
                return FieldReceipt(
                    field_name=spec.name,
                    field_type=spec.field_type,
                    value=spec.value,
                    status="error",
                    attempts=attempt,
                    error=str(exc),
                    validated=True,
                )

        # Exhausted retries
        return FieldReceipt(
            field_name=spec.name,
            field_type=spec.field_type,
            value=spec.value,
            status="error",
            attempts=self._max_retries,
            error=f"Transient error after {self._max_retries} attempts: {last_error}",
            validated=True,
        )

    def _apply_field(self, spec: FieldSpec) -> None:
        """Write the field value into the DOM via the engine."""
        if spec.field_type == "select":
            self._engine.select_option(spec.name, spec.value)
        elif spec.field_type == "checkbox":
            self._engine.fill_field(spec.name, spec.value)
        else:
            self._engine.fill_field(spec.name, spec.value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat()
