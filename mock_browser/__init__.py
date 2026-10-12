"""Mock Browser Engine package for the Computer-Use Back-Office Agent."""

from .engine import MockBrowserEngine
from .dom import DOMNode, DOMDocument
from .portal import MockPortal

__all__ = ["MockBrowserEngine", "DOMNode", "DOMDocument", "MockPortal"]
