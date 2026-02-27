"""Download destination selection and progress screen."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ProgressBar, Static


class DownloadScreen(ModalScreen[str | None]):
    """Modal screen for downloading a file with destination picker."""

    DEFAULT_CSS = """
    DownloadScreen {
        align: center middle;
    }
    DownloadScreen #dialog {
        width: 70;
        height: auto;
        padding: 1 2;
    }
    DownloadScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    DownloadScreen .field-label {
        margin-top: 1;
    }
    DownloadScreen #dest-input {
        width: 100%;
    }
    DownloadScreen #error-label {
        color: red;
        height: 1;
    }
    DownloadScreen #progress {
        width: 100%;
        margin: 1 0;
    }
    DownloadScreen #buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }
    DownloadScreen #buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        bucket: str,
        key: str,
        object_size: int,
        default_dir: str = "",
    ) -> None:
        super().__init__()
        self._bucket = bucket
        self._key = key
        self._object_size = object_size
        self._default_dir = default_dir or str(Path.home() / "Downloads")
        self._downloading = False

    def compose(self) -> ComposeResult:
        filename = self._key.split("/")[-1]
        default_path = os.path.join(self._default_dir, filename)

        with Vertical(id="dialog"):
            yield Label(f"Download: {filename}", id="title")
            yield Static(f"From: {self._bucket}/{self._key}")
            yield Static("Save to:", classes="field-label")
            yield Input(value=default_path, id="dest-input")
            yield Static("", id="error-label")
            yield ProgressBar(total=100, show_eta=False, id="progress")
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Download", variant="success", id="download")

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).update(total=100, progress=0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            self._do_download()
        else:
            if not self._downloading:
                self.dismiss(None)

    def _do_download(self) -> None:
        if self._downloading:
            return

        dest = self.query_one("#dest-input", Input).value.strip()
        if not dest:
            self.query_one("#error-label", Static).update("Destination path is required")
            return

        dest_dir = os.path.dirname(dest)
        if dest_dir and not os.path.isdir(dest_dir):
            self.query_one("#error-label", Static).update(f"Directory does not exist: {dest_dir}")
            return

        self._downloading = True
        self.query_one("#download", Button).disabled = True
        self.query_one("#error-label", Static).update("")

        self._run_download(dest)

    def _run_download(self, local_path: str) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        progress_bar = self.query_one("#progress", ProgressBar)
        downloaded_bytes = 0
        total = max(self._object_size, 1)

        def progress_callback(bytes_transferred: int) -> None:
            nonlocal downloaded_bytes
            downloaded_bytes += bytes_transferred
            pct = min(int((downloaded_bytes / total) * 100), 100)
            self.call_from_thread(progress_bar.update, progress=pct)

        def do_download() -> None:
            try:
                app.r2_client.download_file(
                    self._bucket,
                    self._key,
                    local_path,
                    progress_callback=progress_callback,
                )
                self.call_from_thread(self._download_done, local_path)
            except Exception as e:
                self.call_from_thread(self._download_error, str(e))

        import threading

        threading.Thread(target=do_download, daemon=True).start()

    def _download_done(self, path: str) -> None:
        self.notify(f"Downloaded to: {path}", severity="information")
        self.dismiss(path)

    def _download_error(self, error: str) -> None:
        self._downloading = False
        self.query_one("#download", Button).disabled = False
        self.query_one("#error-label", Static).update(f"Error: {error}")

    def action_cancel(self) -> None:
        if not self._downloading:
            self.dismiss(None)
