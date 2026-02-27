"""Create new bucket modal screen."""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class BucketCreateScreen(ModalScreen[str | None]):
    """Modal dialog for creating a new R2 bucket."""

    DEFAULT_CSS = """
    BucketCreateScreen {
        align: center middle;
    }
    BucketCreateScreen #dialog {
        width: 60;
        height: auto;
        padding: 1 2;
    }
    BucketCreateScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    BucketCreateScreen .field-label {
        margin-top: 1;
    }
    BucketCreateScreen #bucket-name {
        width: 100%;
    }
    BucketCreateScreen #error-label {
        color: red;
        height: 1;
    }
    BucketCreateScreen #buttons {
        width: 100%;
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    BucketCreateScreen #buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Create New Bucket", id="title")
            yield Static("Bucket Name:", classes="field-label")
            yield Input(
                placeholder="my-bucket-name",
                id="bucket-name",
            )
            yield Static("", id="error-label")
            yield Static(
                "Names must be 3-63 chars, lowercase, numbers, hyphens only.",
                classes="hint-text",
            )
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Create", variant="success", id="create")

    def _validate_bucket_name(self, name: str) -> str | None:
        if not name:
            return "Bucket name is required"
        if len(name) < 3:
            return "Name must be at least 3 characters"
        if len(name) > 63:
            return "Name must be at most 63 characters"
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name):
            return "Invalid name: use lowercase, numbers, hyphens; cannot start/end with hyphen"
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            name_input = self.query_one("#bucket-name", Input)
            name = name_input.value.strip()
            error = self._validate_bucket_name(name)
            if error:
                self.query_one("#error-label", Static).update(error)
            else:
                self.dismiss(name)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        error = self._validate_bucket_name(name)
        if error:
            self.query_one("#error-label", Static).update(error)
        else:
            self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
