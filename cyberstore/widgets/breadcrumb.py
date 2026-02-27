"""Breadcrumb path display widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


class Breadcrumb(Widget):
    """Displays the current navigation path as a breadcrumb trail."""

    DEFAULT_CSS = """
    Breadcrumb {
        height: 1;
        padding: 0 1;
    }
    Breadcrumb Static {
        width: auto;
    }
    """

    class PathClicked(Message):
        """Fired when a breadcrumb segment is clicked."""

        def __init__(self, prefix: str) -> None:
            self.prefix = prefix
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._bucket: str = ""
        self._prefix: str = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="breadcrumb-text")

    def set_path(self, bucket: str, prefix: str) -> None:
        """Update the breadcrumb display."""
        self._bucket = bucket
        self._prefix = prefix
        parts = [f"/ {bucket}"]
        if prefix:
            segments = prefix.rstrip("/").split("/")
            for seg in segments:
                parts.append(f" / {seg}")
        text = "".join(parts) + " /"
        try:
            self.query_one("#breadcrumb-text", Static).update(text)
        except Exception:
            pass
