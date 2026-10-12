"""Unit tests for MockBrowserEngine – navigation and DOM interaction."""

import pytest
from mock_browser.engine import MockBrowserEngine, NavigationError
from mock_browser.portal import MockPortal


@pytest.fixture
def engine():
    return MockBrowserEngine()


@pytest.fixture
def logged_in_engine():
    eng = MockBrowserEngine()
    eng.navigate("/login")
    eng.fill_field("username", "admin")
    eng.fill_field("password", "secret")
    eng.submit_form("login-form")
    return eng


class TestNavigation:
    def test_navigate_login(self, engine):
        resp = engine.navigate("/login")
        assert resp.status == 200
        assert engine.current_url == "/login"

    def test_navigate_protected_without_auth(self, engine):
        resp = engine.navigate("/dashboard")
        assert resp.status == 302

    def test_navigate_dashboard_after_login(self, logged_in_engine):
        resp = logged_in_engine.navigate("/dashboard")
        assert resp.status == 200
        assert "Dashboard" in logged_in_engine.title

    def test_history_tracked(self, engine):
        engine.navigate("/login")
        engine.navigate("/login")  # second navigation appends first to history
        assert "/login" in engine.get_history()

    def test_navigate_unknown(self, logged_in_engine):
        resp = logged_in_engine.navigate("/no-such-page")
        assert resp.status == 404


class TestFieldInteraction:
    def test_fill_and_read_text_field(self, engine):
        engine.navigate("/login")
        engine.fill_field("username", "alice")
        assert engine.read_field("username") == "alice"

    def test_fill_password_field(self, engine):
        engine.navigate("/login")
        engine.fill_field("password", "s3cr3t")
        assert engine.read_field("password") == "s3cr3t"

    def test_fill_missing_field_raises(self, engine):
        engine.navigate("/login")
        with pytest.raises(NavigationError):
            engine.fill_field("nonexistent", "value")

    def test_read_missing_field_raises(self, engine):
        engine.navigate("/login")
        with pytest.raises(NavigationError):
            engine.read_field("ghost_field")

    def test_select_option(self, logged_in_engine):
        logged_in_engine.navigate("/form")
        logged_in_engine.select_option("department", "eng")
        assert logged_in_engine.read_field("department") == "eng"

    def test_select_invalid_option_raises(self, logged_in_engine):
        logged_in_engine.navigate("/form")
        with pytest.raises(NavigationError):
            logged_in_engine.select_option("department", "invalid_dept")

    def test_fill_checkbox(self, logged_in_engine):
        logged_in_engine.navigate("/form")
        logged_in_engine.fill_field("agree_terms", True)
        assert logged_in_engine.read_field("agree_terms") is True


class TestFormSubmit:
    def test_login_via_submit_form(self, engine):
        engine.navigate("/login")
        engine.fill_field("username", "operator")
        engine.fill_field("password", "pass123")
        resp = engine.submit_form("login-form")
        assert resp.status == 302
        assert engine.portal.is_authenticated

    def test_data_form_submit_success(self, logged_in_engine):
        logged_in_engine.navigate("/form")
        logged_in_engine.fill_field("first_name", "Jane")
        logged_in_engine.fill_field("last_name", "Doe")
        logged_in_engine.fill_field("email", "jane@example.com")
        logged_in_engine.select_option("department", "hr")
        logged_in_engine.fill_field("agree_terms", True)
        resp = logged_in_engine.submit_form("data-form")
        assert resp.status == 200
        assert "Confirmation" in logged_in_engine.title

    def test_submit_missing_form_raises(self, engine):
        engine.navigate("/login")
        with pytest.raises(NavigationError):
            engine.submit_form("nonexistent-form")


class TestClickAction:
    def test_click_nav_link(self, logged_in_engine):
        logged_in_engine.navigate("/dashboard")
        resp = logged_in_engine.click("nav-submit-form")
        assert resp is not None
        assert "Form" in logged_in_engine.title

    def test_click_submit_button(self, engine):
        engine.navigate("/login")
        engine.fill_field("username", "admin")
        engine.fill_field("password", "secret")
        resp = engine.click("login-btn")
        assert resp is not None
        assert engine.portal.is_authenticated
