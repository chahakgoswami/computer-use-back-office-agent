"""High-level MockBrowserEngine: navigation state + DOM interaction API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .dom import DOMDocument, DOMNode
from .portal import MockPortal, PortalResponse


class NavigationError(Exception):
    """Raised when a navigation or interaction fails."""


class MockBrowserEngine:
    """
    Simulated browser engine.

    Maintains:
      - current URL / document
      - navigation history
      - cookie-like session (delegated to MockPortal)

    Provides a simple imperative API:
      navigate(url)  -> PortalResponse
      find(...)      -> DOMNode | None
      fill(name, v)  -> None
      click(id)      -> PortalResponse
      submit(form_id)-> PortalResponse
    """

    def __init__(self, portal: Optional[MockPortal] = None) -> None:
        self.portal = portal or MockPortal()
        self._current_url: str = ""
        self._current_doc: Optional[DOMDocument] = None
        self._history: List[str] = []

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> PortalResponse:
        """Issue a GET to *url* and update the current document."""
        response = self.portal.get(url)
        self._apply_response(url, response)
        return response

    def _apply_response(
        self, requested_url: str, response: PortalResponse
    ) -> None:
        """Update navigation state from a response (follow single redirect)."""
        if self._current_url:
            self._history.append(self._current_url)
        effective_url = response.redirect or requested_url
        self._current_url = effective_url
        self._current_doc = response.document

    # ------------------------------------------------------------------
    # DOM querying
    # ------------------------------------------------------------------

    @property
    def current_url(self) -> str:
        return self._current_url

    @property
    def document(self) -> Optional[DOMDocument]:
        return self._current_doc

    @property
    def title(self) -> str:
        return self._current_doc.title if self._current_doc else ""

    def find(self, tag: Optional[str] = None, **attrs) -> Optional[DOMNode]:
        """Find the first DOM node matching tag and attributes."""
        if not self._current_doc:
            return None
        return self._current_doc.find(tag, **attrs)

    def find_all(self, tag: Optional[str] = None, **attrs) -> List[DOMNode]:
        """Find all DOM nodes matching tag and attributes."""
        if not self._current_doc:
            return []
        return self._current_doc.find_all(tag, **attrs)

    def get_element_by_id(self, element_id: str) -> Optional[DOMNode]:
        if not self._current_doc:
            return None
        return self._current_doc.get_element_by_id(element_id)

    # ------------------------------------------------------------------
    # Field interaction
    # ------------------------------------------------------------------

    def read_field(self, name: str) -> Any:
        """Return the current value of a field identified by *name*."""
        if not self._current_doc:
            raise NavigationError("No document loaded.")
        nodes = self._current_doc.get_elements_by_name(name)
        if not nodes:
            # Also try by id
            node = self._current_doc.get_element_by_id(name)
            if node is None:
                raise NavigationError(f"Field not found: {name!r}")
            nodes = [node]
        node = nodes[0]
        if node.tag == "input" and node.type in ("checkbox", "radio"):
            return node.checked
        return node.value

    def fill_field(self, name: str, value: Any) -> None:
        """Set the value of a form field identified by *name*."""
        if not self._current_doc:
            raise NavigationError("No document loaded.")
        nodes = self._current_doc.get_elements_by_name(name)
        if not nodes:
            node = self._current_doc.get_element_by_id(name)
            if node is None:
                raise NavigationError(f"Field not found: {name!r}")
            nodes = [node]
        node = nodes[0]
        if node.disabled:
            raise NavigationError(f"Field {name!r} is disabled.")
        if node.tag == "input" and node.type in ("checkbox", "radio"):
            node.checked = bool(value)
        else:
            node.value = value

    def select_option(self, name: str, option_value: str) -> None:
        """Set a <select> element to *option_value*."""
        if not self._current_doc:
            raise NavigationError("No document loaded.")
        nodes = self._current_doc.get_elements_by_name(name)
        if not nodes:
            node = self._current_doc.get_element_by_id(name)
            if node is None:
                raise NavigationError(f"Select element not found: {name!r}")
            nodes = [node]
        node = nodes[0]
        if node.tag != "select":
            raise NavigationError(f"{name!r} is not a <select> element.")
        valid = [c.attrs.get("value") for c in node.children]
        if option_value not in valid:
            raise NavigationError(
                f"Option {option_value!r} not in {valid} for field {name!r}"
            )
        node.value = option_value

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def click(self, element_id: str) -> Optional[PortalResponse]:
        """Simulate clicking an element (button / link)."""
        node = self.get_element_by_id(element_id)
        if node is None:
            raise NavigationError(f"Element not found: {element_id!r}")
        if node.tag == "a":
            href = node.attrs.get("href", "")
            return self.navigate(href)
        if node.tag == "button":
            # Find parent form and submit
            form = self._find_parent_form(element_id)
            if form:
                return self._submit_form_node(form)
        return None

    def submit_form(self, form_id: str) -> PortalResponse:
        """Collect and POST a form by its id."""
        form = self.get_element_by_id(form_id)
        if form is None or form.tag != "form":
            raise NavigationError(f"Form not found: {form_id!r}")
        return self._submit_form_node(form)

    def _submit_form_node(self, form: DOMNode) -> PortalResponse:
        action = form.attrs.get("action", "/")
        # Gather all input / select / textarea values
        data: Dict[str, Any] = {}
        for node in form.find_all("input"):
            n = node.name or node.id
            if not n:
                continue
            if node.type in ("checkbox", "radio"):
                data[n] = node.checked
            elif node.type == "submit":
                pass  # skip submit buttons
            else:
                data[n] = node.value
        for node in form.find_all("select"):
            n = node.name or node.id
            if n:
                data[n] = node.value
        for node in form.find_all("textarea"):
            n = node.name or node.id
            if n:
                data[n] = node.value
        response = self.portal.post(action, data)
        self._apply_response(action, response)
        return response

    def _find_parent_form(self, element_id: str) -> Optional[DOMNode]:
        """Walk all forms in the document and return the one containing *element_id*."""
        if not self._current_doc:
            return None
        for form in self._current_doc.find_all("form"):
            if form.find(id=element_id):
                return form
        return None

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def back(self) -> Optional[PortalResponse]:
        """Navigate to the previous URL in history."""
        if not self._history:
            return None
        prev = self._history.pop()
        return self.navigate(prev)

    def get_history(self) -> List[str]:
        return list(self._history)

    def __repr__(self) -> str:
        return (
            f"MockBrowserEngine(url={self._current_url!r}, "
            f"title={self.title!r})"
        )
