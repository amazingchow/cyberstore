"""Delete confirmation modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class DeleteConfirmScreen(ModalScreen[bool]):
    """Modal dialog to confirm object/bucket deletion."""

    DEFAULT_CSS = """
    DeleteConfirmScreen {
        align: center middle;
    }
    DeleteConfirmScreen #dialog {
        width: 60;
        height: auto;
        max-height: 20;
        padding: 1 2;
    }
    DeleteConfirmScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    DeleteConfirmScreen .file-list {
        height: auto;
        max-height: 8;
        margin: 1 0;
        padding: 0 1;
    }
    DeleteConfirmScreen #buttons {
        width: 100%;
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    DeleteConfirmScreen #buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, items: list[str], is_bucket: bool = False) -> None:
        super().__init__()
        self._items = items
        self._is_bucket = is_bucket

    def compose(self) -> ComposeResult:
        kind = "bucket" if self._is_bucket else "object"
        count = len(self._items)
        title = f"Delete {count} {kind}{'s' if count > 1 else ''}?"

        with Vertical(id="dialog"):
            yield Label(title, id="title")
            yield Static("This action cannot be undone.", classes="warning-text")
            with Vertical(classes="file-list"):
                for item in self._items[:10]:
                    name = item.split("/")[-1] if "/" in item else item
                    yield Static(f"  ✕ {name}")
                if len(self._items) > 10:
                    yield Static(f"  ... and {len(self._items) - 10} more")
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Delete", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
