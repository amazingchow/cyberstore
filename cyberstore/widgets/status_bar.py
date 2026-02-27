"""Status bar widget for connection and bucket info."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Bottom status bar showing connection state and current context."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        padding: 0 1;
        layout: horizontal;
    }
    StatusBar .status-segment {
        width: auto;
        margin: 0 2 0 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._connected = False
        self._bucket = ""
        self._count = 0
        self._total_size = ""

    def compose(self) -> ComposeResult:
        yield Static("● Disconnected", id="status-conn", classes="status-segment")
        yield Static("", id="status-bucket", classes="status-segment")
        yield Static("", id="status-count", classes="status-segment")
        yield Static("", id="status-size", classes="status-segment")

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        label = "● Connected" if connected else "● Disconnected"
        try:
            self.query_one("#status-conn", Static).update(label)
        except Exception:
            pass

    def set_bucket(self, name: str) -> None:
        self._bucket = name
        try:
            self.query_one("#status-bucket", Static).update(name if name else "")
        except Exception:
            pass

    def set_object_info(self, count: int, total_size: str) -> None:
        self._count = count
        self._total_size = total_size
        try:
            self.query_one("#status-count", Static).update(
                f"{count} object{'s' if count != 1 else ''}" if count else ""
            )
            self.query_one("#status-size", Static).update(total_size)
        except Exception:
            pass
