"""Create new folder (virtual prefix) modal screen."""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class FolderCreateScreen(ModalScreen[str | None]):
    """Modal dialog for creating a new virtual folder inside a bucket prefix."""

    DEFAULT_CSS = """
    FolderCreateScreen #folder-name {
        width: 100%;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, bucket: str, prefix: str = "") -> None:
        super().__init__()
        self._bucket = bucket
        self._prefix = prefix

    def compose(self) -> ComposeResult:
        location = f"{self._bucket}/{self._prefix}" if self._prefix else self._bucket
        with Vertical(id="dialog"):
            yield Label("Create New Folder", id="title")
            with Vertical(id="main-body"):
                yield Static(f"Location: {location}", classes="hint-text")
                yield Static("Folder Name:", classes="field-label")
                yield Input(
                    placeholder="my-folder",
                    id="folder-name",
                )
                yield Static("", id="error-label")
                yield Static(
                    "Use letters, numbers, hyphens, underscores, and dots.",
                    classes="hint-text",
                )
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Create", variant="success", id="create")

    def _validate_folder_name(self, name: str) -> str | None:
        if not name:
            return "Folder name is required"
        if "/" in name:
            return "Folder name cannot contain '/'"
        if not re.match(r"^[A-Za-z0-9._\-]+$", name):
            return "Invalid name: use letters, numbers, hyphens, underscores, dots"
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#folder-name", Input).value.strip()
        error = self._validate_folder_name(name)
        if error:
            self.query_one("#error-label", Static).update(error)
        else:
            self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
