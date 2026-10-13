"""Mock portal session manager – owns the engine and tracks session state."""

from __future__ import annotations

from typing import Any, Dict, Optional

from mock_browser.engine import MockBrowserEngine
from mock_browser.portal import MockPortal


class SessionManager:
    """
    Wraps a MockBrowserEngine and provides convenience methods for
    establishing and inspecting a portal session.

    Attributes
    ----------
    engine : MockBrowserEngine
        The underlying browser engine shared across tasks.
    """

    def __init__(
        self,
        portal: Optional[MockPortal] = None,
        engine: Optional[MockBrowserEngine] = None,
    ) -> None:
        if engine is not None:
            self._engine = engine
        else:
            self._engine = MockBrowserEngine(portal=portal)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def engine(self) -> MockBrowserEngine:
        return self._engine

    @property
    def portal(self) -> MockPortal:
        return self._engine.portal

    @property
    def is_authenticated(self) -> bool:
        return self._engine.portal.is_authenticated

    @property
    def current_url(self) -> str:
        return self._engine.current_url

    @property
    def title(self) -> str:
        return self._engine.title

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> bool:
        """
        Perform the standard login flow.

        Returns True on success, False on failure.
        """
        self._engine.navigate("/login")
        self._engine.fill_field("username", username)
        self._engine.fill_field("password", password)
        resp = self._engine.submit_form("login-form")
        return self.portal.is_authenticated

    def logout(self) -> None:
        """Navigate to /logout to terminate the session."""
        self._engine.navigate("/logout")

    def reset(self) -> None:
        """
        Hard-reset: discard the current engine and portal, create fresh ones.
        """
        self._engine = MockBrowserEngine()

    # ------------------------------------------------------------------
    # Convenience passthrough
    # ------------------------------------------------------------------

    def navigate(self, url: str):
        return self._engine.navigate(url)

    def read_field(self, name: str) -> Any:
        return self._engine.read_field(name)

    def fill_field(self, name: str, value: Any) -> None:
        self._engine.fill_field(name, value)

    def select_option(self, name: str, value: str) -> None:
        self._engine.select_option(name, value)

    def click(self, element_id: str):
        return self._engine.click(element_id)

    def submit_form(self, form_id: str):
        return self._engine.submit_form(form_id)

    def __repr__(self) -> str:
        auth = "authenticated" if self.is_authenticated else "anonymous"
        return (
            f"SessionManager({auth}, url={self.current_url!r})"
        )
