"""Unit tests for the DOMNode and DOMDocument classes."""

import pytest
from mock_browser.dom import DOMNode, DOMDocument


def _make_doc() -> DOMDocument:
    root = DOMNode(tag="html")
    body = DOMNode(tag="body")
    form = DOMNode(tag="form", attrs={"id": "test-form"})
    inp = DOMNode(tag="input",
                  attrs={"name": "username", "id": "username", "type": "text"})
    pwd = DOMNode(tag="input",
                  attrs={"name": "password", "id": "password",
                         "type": "password"})
    cb = DOMNode(tag="input",
                 attrs={"name": "remember", "id": "remember",
                        "type": "checkbox"})
    form.children.extend([inp, pwd, cb])
    body.children.append(form)
    root.children.append(body)
    return DOMDocument(title="Test", root=root)


class TestDOMNode:
    def test_id_attr(self):
        node = DOMNode(tag="input", attrs={"id": "foo"})
        assert node.id == "foo"

    def test_name_attr(self):
        node = DOMNode(tag="input", attrs={"name": "bar"})
        assert node.name == "bar"

    def test_value_default(self):
        node = DOMNode(tag="input", attrs={"value": "hello"})
        assert node.value == "hello"

    def test_value_setter(self):
        node = DOMNode(tag="input", attrs={})
        node.value = "world"
        assert node.value == "world"

    def test_checked_default(self):
        node = DOMNode(tag="input", attrs={"type": "checkbox"})
        assert node.checked is False

    def test_checked_setter(self):
        node = DOMNode(tag="input", attrs={"type": "checkbox"})
        node.checked = True
        assert node.checked is True

    def test_find_all_by_tag(self):
        parent = DOMNode(tag="div")
        for _ in range(3):
            parent.children.append(DOMNode(tag="span"))
        parent.children.append(DOMNode(tag="p"))
        spans = parent.find_all("span")
        assert len(spans) == 3

    def test_find_by_attr(self):
        parent = DOMNode(tag="div")
        parent.children.append(DOMNode(tag="input", attrs={"id": "target"}))
        parent.children.append(DOMNode(tag="input", attrs={"id": "other"}))
        found = parent.find("input", id="target")
        assert found is not None
        assert found.id == "target"

    def test_find_returns_none_when_missing(self):
        parent = DOMNode(tag="div")
        assert parent.find("input") is None


class TestDOMDocument:
    def test_get_element_by_id(self):
        doc = _make_doc()
        node = doc.get_element_by_id("username")
        assert node is not None
        assert node.id == "username"

    def test_get_element_by_id_missing(self):
        doc = _make_doc()
        assert doc.get_element_by_id("nonexistent") is None

    def test_get_elements_by_name(self):
        doc = _make_doc()
        nodes = doc.get_elements_by_name("username")
        assert len(nodes) == 1

    def test_get_form_data_text_fields(self):
        doc = _make_doc()
        doc.get_element_by_id("username").value = "alice"
        doc.get_element_by_id("password").value = "secret"
        data = doc.get_form_data()
        assert data["username"] == "alice"
        assert data["password"] == "secret"

    def test_get_form_data_checkbox(self):
        doc = _make_doc()
        doc.get_element_by_id("remember").checked = True
        data = doc.get_form_data()
        assert data["remember"] is True
