"""Data-extraction module: scrapes simulated portal pages into structured JSON."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mock_browser.engine import MockBrowserEngine, NavigationError
from mock_browser.portal import PortalResponse


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ExtractionError(Exception):
    """Raised when page scraping fails."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """
    Structured result of a single page extraction.

    Attributes
    ----------
    url : str
        The portal URL that was scraped.
    page_type : str
        Detected page type: ``"table"``, ``"confirmation"``, or ``"unknown"``.
    data : list | dict
        Extracted payload.  For table pages a list of row dicts; for
        confirmation pages a dict with ``message`` and ``ref_id``.
    extracted_at : str
        ISO-8601 timestamp.
    saved_path : str | None
        File-system path where the JSON was saved (set after ``save()``).
    error : str | None
        Non-empty only when extraction encountered a problem.
    """
    url: str
    page_type: str
    data: Any
    extracted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    saved_path: Optional[str] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        rows = len(self.data) if isinstance(self.data, list) else "-"
        return (
            f"ExtractionResult(url={self.url!r}, type={self.page_type}, "
            f"rows={rows}, saved={self.saved_path!r})"
        )


# ---------------------------------------------------------------------------
# DataExtractor
# ---------------------------------------------------------------------------

class DataExtractor:
    """
    Scrapes portal pages reachable by the engine and saves JSON output.

    Parameters
    ----------
    engine : MockBrowserEngine
        An authenticated browser engine.
    results_dir : str
        Directory where JSON result files are written.  Created on first use
        if it does not exist.
    """

    def __init__(
        self,
        engine: MockBrowserEngine,
        results_dir: str = "results",
    ) -> None:
        self._engine = engine
        self._results_dir = results_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_page(self, url: str, *, save: bool = True) -> ExtractionResult:
        """
        Navigate to *url* and extract its contents.

        Supports two simulated page types:

        * **Table pages** – identified by a ``<table id="records-table">``.
          Each ``<tr>`` in ``<tbody>`` is mapped to a dict keyed by the
          ``<th>`` column headers.
        * **Confirmation pages** – identified by a ``<p id="confirm-message">``.
          Returns ``{"message": ..., "ref_id": ...}``.

        Parameters
        ----------
        url : str
            Portal URL to GET and scrape.
        save : bool
            If True, write the result JSON to ``results_dir``.

        Returns
        -------
        ExtractionResult
        """
        try:
            resp = self._engine.navigate(url)
        except Exception as exc:  # noqa: BLE001
            return ExtractionResult(
                url=url,
                page_type="unknown",
                data=None,
                error=f"Navigation failed: {exc}",
            )

        if resp.status >= 400:
            return ExtractionResult(
                url=url,
                page_type="unknown",
                data=None,
                error=f"HTTP {resp.status} when loading {url!r}",
            )

        doc = resp.document
        result = self._scrape_document(url, doc)

        if save and result.ok:
            result.saved_path = self._save_result(result)

        return result

    def extract_from_response(
        self,
        url: str,
        response: PortalResponse,
        *,
        save: bool = True,
    ) -> ExtractionResult:
        """
        Extract data directly from an existing *response* (no extra navigation).

        Useful when the caller already has the response from a previous action
        (e.g. immediately after a form submission).
        """
        if response.status >= 400:
            return ExtractionResult(
                url=url,
                page_type="unknown",
                data=None,
                error=f"HTTP {response.status} when loading {url!r}",
            )

        result = self._scrape_document(url, response.document)

        if save and result.ok:
            result.saved_path = self._save_result(result)

        return result

    # ------------------------------------------------------------------
    # Scraping helpers
    # ------------------------------------------------------------------

    def _scrape_document(self, url: str, doc) -> ExtractionResult:
        """Detect page type and delegate to the appropriate scraper."""
        # --- confirmation page ---
        confirm_node = doc.get_element_by_id("confirm-message")
        if confirm_node is not None:
            return self._scrape_confirmation(url, doc)

        # --- table page ---
        table_node = doc.get_element_by_id("records-table")
        if table_node is not None:
            return self._scrape_table(url, doc, table_node)

        # --- fallback: collect all text nodes ---
        return ExtractionResult(
            url=url,
            page_type="unknown",
            data={"title": doc.title},
            error=None,
        )

    def _scrape_table(
        self, url: str, doc, table_node
    ) -> ExtractionResult:
        """Extract rows from a <table id="records-table">."""
        # Column headers from <thead> <th> nodes
        thead = table_node.find("thead")
        headers: List[str] = []
        if thead:
            for th in thead.find_all("th"):
                headers.append(th.text.strip())

        # Row data from <tbody> <tr> nodes
        tbody = table_node.find("tbody")
        rows: List[Dict[str, str]] = []
        if tbody:
            for tr in tbody.find_all("tr"):
                cells = tr.find_all("td")
                if headers:
                    row = {}
                    for i, hdr in enumerate(headers):
                        row[hdr] = cells[i].text.strip() if i < len(cells) else ""
                else:
                    row = {str(i): td.text.strip() for i, td in enumerate(cells)}
                rows.append(row)

        return ExtractionResult(
            url=url,
            page_type="table",
            data=rows,
        )

    def _scrape_confirmation(self, url: str, doc) -> ExtractionResult:
        """Extract message and ref_id from a confirmation page."""
        msg_node = doc.get_element_by_id("confirm-message")
        ref_node = doc.get_element_by_id("ref-id")

        message = msg_node.text.strip() if msg_node else ""
        ref_raw = ref_node.text.strip() if ref_node else ""
        # ref_raw looks like "Reference ID: TXN-00001" – extract the id part
        ref_id = ref_raw.replace("Reference ID:", "").strip() if ref_raw else ""

        return ExtractionResult(
            url=url,
            page_type="confirmation",
            data={"message": message, "ref_id": ref_id},
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_result(self, result: ExtractionResult) -> str:
        """Serialize *result* to a JSON file and return its path."""
        os.makedirs(self._results_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        safe_url = result.url.strip("/").replace("/", "_") or "root"
        filename = f"{safe_url}_{result.page_type}_{ts}.json"
        filepath = os.path.join(self._results_dir, filename)
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(result.as_dict(), fh, indent=2)
        return filepath
