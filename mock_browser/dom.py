"""Simulated DOM structures for the mock browser engine."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DOMNode:
    """Represents a single node in the simulated DOM tree."""

    tag: str
    attrs: Dict[str, Any] = field(default_factory=dict)
    text: str = ""
    children: List["DOMNode"] = field(default_factory=list)

    # Runtime state for interactive elements
    _value: Any = field(default=None, repr=False)
    _checked: bool = field(default=False, repr=False)
    _disabled: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def id(self) -> Optional[str]:
        return self.attrs.get("id")

    @property
    def name(self) -> Optional[str]:
        return self.attrs.get("name")

    @property
    def type(self) -> Optional[str]:
        return self.attrs.get("type", "").lower()

    @property
    def value(self) -> Any:
        return self._value if self._value is not None else self.attrs.get("value", "")

    @value.setter
    def value(self, v: Any) -> None:
        self._value = v

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, v: bool) -> None:
        self._checked = v

    @property
    def disabled(self) -> bool:
        return self._disabled

    @disabled.setter
    def disabled(self, v: bool) -> None:
        self._disabled = v

    def get_attr(self, key: str, default: Any = None) -> Any:
        return self.attrs.get(key, default)

    def find_all(self, tag: Optional[str] = None, **attr_filters) -> List["DOMNode"]:
        """Recursively find descendant nodes matching tag and/or attributes."""
        results: List[DOMNode] = []
        for child in self.children:
            match = True
            if tag and child.tag != tag:
                match = False
            for k, v in attr_filters.items():
                if child.attrs.get(k) != v:
                    match = False
                    break
            if match:
                results.append(child)
            results.extend(child.find_all(tag, **attr_filters))
        return results

    def find(self, tag: Optional[str] = None, **attr_filters) -> Optional["DOMNode"]:
        """Return the first matching descendant or None."""
        results = self.find_all(tag, **attr_filters)
        return results[0] if results else None

    def __repr__(self) -> str:
        attr_str = " ".join(f'{k}="{v}"' for k, v in self.attrs.items())
        return f"<{self.tag} {attr_str}>{self.text}</{self.tag}>"


class DOMDocument:
    """Root document holding the full DOM tree for a simulated page."""

    def __init__(self, title: str, root: DOMNode) -> None:
        self.title = title
        self.root = root

    def find_all(self, tag: Optional[str] = None, **attr_filters) -> List[DOMNode]:
        return self.root.find_all(tag, **attr_filters)

    def find(self, tag: Optional[str] = None, **attr_filters) -> Optional[DOMNode]:
        return self.root.find(tag, **attr_filters)

    def get_element_by_id(self, element_id: str) -> Optional[DOMNode]:
        return self.root.find(id=element_id)

    def get_elements_by_name(self, name: str) -> List[DOMNode]:
        return self.root.find_all(name=name)

    def get_form_data(self) -> Dict[str, Any]:
        """Collect current values of all form inputs."""
        data: Dict[str, Any] = {}
        for node in self.find_all("input"):
            n = node.name or node.id
            if not n:
                continue
            if node.type in ("checkbox", "radio"):
                data[n] = node.checked
            else:
                data[n] = node.value
        for node in self.find_all("select"):
            n = node.name or node.id
            if n:
                data[n] = node.value
        for node in self.find_all("textarea"):
            n = node.name or node.id
            if n:
                data[n] = node.value
        return data

    def __repr__(self) -> str:
        return f"DOMDocument(title={self.title!r})"
