"""Search/filter bar widget."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Input


class SearchBar(Input):
    """Input widget for filtering objects by name."""

    class SearchChanged(Message):
        """Fired when the search text changes."""

        def __init__(self, query: str) -> None:
            self.query = query
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(
            placeholder="Search objects...",
            **kwargs,
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        self.post_message(self.SearchChanged(event.value))
