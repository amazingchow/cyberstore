"""Upload file screen with directory tree picker and progress."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Input,
    Label,
    ProgressBar,
    Static,
)

from cyberstore.utils import MAX_OBJECT_SIZE, format_size


class UploadScreen(ModalScreen[str | None]):
    """Modal screen for selecting and uploading a file."""

    DEFAULT_CSS = """
    UploadScreen {
        align: center middle;
    }
    UploadScreen #dialog {
        width: 80;
        height: 30;
        padding: 1 2;
    }
    UploadScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    UploadScreen #file-tree {
        height: 1fr;
        margin: 1 0;
    }
    UploadScreen #selected-file {
        height: 1;
        padding: 0 1;
    }
    UploadScreen #file-size-info {
        height: 1;
        padding: 0 1;
    }
    UploadScreen #error-label {
        color: red;
        height: 1;
    }
    UploadScreen #key-input {
        width: 100%;
    }
    UploadScreen #progress {
        width: 100%;
        margin: 1 0;
    }
    UploadScreen #buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }
    UploadScreen #buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, bucket: str, prefix: str = "") -> None:
        super().__init__()
        self._bucket = bucket
        self._prefix = prefix
        self._selected_path: str | None = None
        self._uploading = False

    def compose(self) -> ComposeResult:
        home = str(Path.home())
        with Vertical(id="dialog"):
            yield Label(f"Upload to: {self._bucket}/{self._prefix}", id="title")
            yield DirectoryTree(home, id="file-tree")
            yield Static("No file selected", id="selected-file")
            yield Static("", id="file-size-info")
            yield Static("", id="error-label")
            yield Static("Object key (path in bucket):", classes="field-label")
            yield Input(value=self._prefix, placeholder="path/to/file.ext", id="key-input")
            yield ProgressBar(total=100, show_eta=False, id="progress")
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Upload", variant="success", id="upload")

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).update(total=100, progress=0)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = str(event.path)
        self._selected_path = path
        filename = os.path.basename(path)
        file_size = os.path.getsize(path)

        self.query_one("#selected-file", Static).update(f"Selected: {filename}")
        self.query_one("#file-size-info", Static).update(f"Size: {format_size(file_size)}")

        if file_size > MAX_OBJECT_SIZE:
            self.query_one("#error-label", Static).update(f"File exceeds 10 MB limit ({format_size(file_size)})")
        else:
            self.query_one("#error-label", Static).update("")

        key_input = self.query_one("#key-input", Input)
        if not key_input.value or key_input.value == self._prefix:
            key_input.value = self._prefix + filename

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "upload":
            self._do_upload()
        else:
            if not self._uploading:
                self.dismiss(None)

    def _do_upload(self) -> None:
        if self._uploading:
            return
        if not self._selected_path:
            self.query_one("#error-label", Static).update("No file selected")
            return

        file_size = os.path.getsize(self._selected_path)
        if file_size > MAX_OBJECT_SIZE:
            self.query_one("#error-label", Static).update(f"File exceeds 10 MB limit ({format_size(file_size)})")
            return

        key = self.query_one("#key-input", Input).value.strip()
        if not key:
            self.query_one("#error-label", Static).update("Object key is required")
            return

        self._uploading = True
        self.query_one("#upload", Button).disabled = True
        self.query_one("#error-label", Static).update("")

        self._run_upload(self._selected_path, key, file_size)

    def _run_upload(self, local_path: str, key: str, file_size: int) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        progress_bar = self.query_one("#progress", ProgressBar)
        uploaded_bytes = 0

        def progress_callback(bytes_transferred: int) -> None:
            nonlocal uploaded_bytes
            uploaded_bytes += bytes_transferred
            pct = min(int((uploaded_bytes / file_size) * 100), 100)
            self.call_from_thread(progress_bar.update, progress=pct)

        def do_upload() -> None:
            try:
                app.r2_client.upload_file(self._bucket, local_path, key, progress_callback=progress_callback)
                self.call_from_thread(self._upload_done, key)
            except Exception as e:
                self.call_from_thread(self._upload_error, str(e))

        import threading

        threading.Thread(target=do_upload, daemon=True).start()

    def _upload_done(self, key: str) -> None:
        self.notify(f"Uploaded: {key}", severity="information")
        self.dismiss(key)

    def _upload_error(self, error: str) -> None:
        self._uploading = False
        self.query_one("#upload", Button).disabled = False
        self.query_one("#error-label", Static).update(f"Error: {error}")

    def action_cancel(self) -> None:
        if not self._uploading:
            self.dismiss(None)
