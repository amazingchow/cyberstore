"""CDN / presigned URL display modal with clipboard copy."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

try:
    import pyperclip

    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class LinkScreen(ModalScreen):
    """Modal showing CDN and presigned URLs for an object."""

    DEFAULT_CSS = """
    LinkScreen .url-label {
        margin-top: 1;
        text-style: bold;
    }
    LinkScreen .url-input {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        object_key: str,
        cdn_url: str | None = None,
        presigned_url: str | None = None,
    ) -> None:
        super().__init__()
        self._object_key = object_key
        self._cdn_url = cdn_url
        self._presigned_url = presigned_url

    def compose(self) -> ComposeResult:
        name = self._object_key.split("/")[-1]
        with Vertical(id="dialog"):
            yield Label(f"Links: {name}", id="title")

            with Vertical(id="main-body"):
                if self._cdn_url:
                    yield Static("CDN URL:", classes="url-label")
                    yield Input(value=self._cdn_url, id="cdn-url", classes="url-input")
                else:
                    yield Static("CDN URL: Not configured (set custom domain in settings)", classes="url-label")
                    if self._presigned_url:
                        yield Static("Presigned URL:", classes="url-label")
                        yield Input(value=self._presigned_url, id="presigned-url", classes="url-input")
                    else:
                        yield Static("Presigned URL: Not configured", classes="url-label")

            with Horizontal(id="buttons"):
                yield Button("Copy URL", variant="primary", id="copy-url")
                yield Button("Cancel", variant="default", id="cancel")

    def _copy_to_clipboard(self, text: str) -> None:
        if HAS_PYPERCLIP:
            try:
                pyperclip.copy(text)
                self.notify("Copied to clipboard!", severity="information")
                return
            except Exception:
                pass
        self.notify("Could not copy to clipboard", severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-url":
            if self._cdn_url:
                self._copy_to_clipboard(self._cdn_url)
            elif self._presigned_url:
                self._copy_to_clipboard(self._presigned_url)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
