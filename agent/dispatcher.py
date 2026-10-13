"""Action dispatcher: maps action names to MockBrowserEngine calls."""

from __future__ import annotations

from typing import Any, Dict

from mock_browser.engine import MockBrowserEngine, NavigationError


class DispatchError(Exception):
    """Raised when an action cannot be dispatched."""


class ActionDispatcher:
    """
    Translates a high-level action dict into MockBrowserEngine method calls.

    Supported actions
    -----------------
    navigate   : {"url": str}
    read_field : {"name": str}
    fill_field : {"name": str, "value": Any}
    select_option : {"name": str, "value": str}
    click      : {"element_id": str}
    submit_form: {"form_id": str}
    """

    def __init__(self, engine: MockBrowserEngine) -> None:
        self._engine = engine
        self._dispatch_table = {
            "navigate": self._navigate,
            "read_field": self._read_field,
            "fill_field": self._fill_field,
            "select_option": self._select_option,
            "click": self._click,
            "submit_form": self._submit_form,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(self, action: str, params: Dict[str, Any]) -> Any:
        """
        Execute *action* with *params*.

        Returns
        -------
        Any
            The meaningful return value of the action (e.g. field value,
            response status string).

        Raises
        ------
        DispatchError
            When the action name is unknown.
        NavigationError
            When the underlying engine call fails (re-raised transparently).
        """
        handler = self._dispatch_table.get(action)
        if handler is None:
            raise DispatchError(
                f"Unknown action {action!r}. "
                f"Available: {list(self._dispatch_table)}"
            )
        return handler(**params)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _navigate(self, url: str) -> str:
        resp = self._engine.navigate(url)
        return f"status={resp.status} url={self._engine.current_url!r}"

    def _read_field(self, name: str) -> Any:
        return self._engine.read_field(name)

    def _fill_field(self, name: str, value: Any) -> str:
        self._engine.fill_field(name, value)
        return f"filled {name!r}={value!r}"

    def _select_option(self, name: str, value: str) -> str:
        self._engine.select_option(name, value)
        return f"selected {name!r}={value!r}"

    def _click(self, element_id: str) -> str:
        resp = self._engine.click(element_id)
        status = resp.status if resp else "no-response"
        return f"clicked {element_id!r} status={status}"

    def _submit_form(self, form_id: str) -> str:
        resp = self._engine.submit_form(form_id)
        return f"submitted {form_id!r} status={resp.status}"
