"""CDN / presigned URL display modal with clipboard copy."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
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
    LinkScreen {
        align: center middle;
    }
    LinkScreen #dialog {
        width: 80;
        height: auto;
        padding: 1 2;
    }
    LinkScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    LinkScreen .url-label {
        margin-top: 1;
        text-style: bold;
    }
    LinkScreen .url-input {
        width: 100%;
        margin-bottom: 0;
    }
    LinkScreen .copy-btn {
        width: 100%;
        margin-bottom: 1;
    }
    LinkScreen #close-btn {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
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

            if self._cdn_url:
                yield Static("CDN URL:", classes="url-label")
                yield Input(value=self._cdn_url, id="cdn-url", classes="url-input")
                yield Button("Copy CDN URL", variant="primary", id="copy-cdn", classes="copy-btn")
            else:
                yield Static(
                    "CDN URL: Not configured (set custom domain in settings)",
                    classes="url-label",
                )

            if self._presigned_url:
                yield Static("Presigned URL:", classes="url-label")
                yield Input(
                    value=self._presigned_url,
                    id="presigned-url",
                    classes="url-input",
                )
                yield Button(
                    "Copy Presigned URL",
                    variant="primary",
                    id="copy-presigned",
                    classes="copy-btn",
                )

            yield Button("Close", variant="default", id="close-btn")

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
        if event.button.id == "copy-cdn" and self._cdn_url:
            self._copy_to_clipboard(self._cdn_url)
        elif event.button.id == "copy-presigned" and self._presigned_url:
            self._copy_to_clipboard(self._presigned_url)
        elif event.button.id == "close-btn":
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
