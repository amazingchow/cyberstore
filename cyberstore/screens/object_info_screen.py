"""Object metadata information modal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from cyberstore.utils import format_size


class ObjectInfoScreen(ModalScreen):
    """Modal displaying detailed object metadata."""

    DEFAULT_CSS = """
    ObjectInfoScreen {
        align: center middle;
    }
    ObjectInfoScreen #dialog {
        width: 65;
        height: auto;
        padding: 1 2;
    }
    ObjectInfoScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    ObjectInfoScreen .info-row {
        height: 1;
        padding: 0 1;
    }
    ObjectInfoScreen #close-btn {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, metadata: dict[str, Any]) -> None:
        super().__init__()
        self._metadata = metadata

    def compose(self) -> ComposeResult:
        meta = self._metadata
        key = meta.get("key", "Unknown")
        name = key.split("/")[-1] if "/" in key else key

        with Vertical(id="dialog"):
            yield Static(f"Object Info: {name}", id="title")
            yield Static(f"  Key:          {key}", classes="info-row")
            yield Static(
                f"  Size:         {format_size(meta.get('size', 0))}",
                classes="info-row",
            )
            yield Static(
                f"  Content Type: {meta.get('content_type', 'N/A')}",
                classes="info-row",
            )

            modified = meta.get("last_modified")
            if isinstance(modified, datetime):
                mod_str = modified.strftime("%Y-%m-%d %H:%M:%S UTC")
                ago = humanize.naturaltime(datetime.now(modified.tzinfo) - modified)
                yield Static(f"  Modified:     {mod_str} ({ago})", classes="info-row")
            elif modified:
                yield Static(f"  Modified:     {modified}", classes="info-row")

            yield Static(f"  ETag:         {meta.get('etag', 'N/A')}", classes="info-row")

            extra_meta = meta.get("metadata", {})
            if extra_meta:
                yield Static("  Metadata:", classes="info-row")
                for k, v in extra_meta.items():
                    yield Static(f"    {k}: {v}", classes="info-row")

            yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
