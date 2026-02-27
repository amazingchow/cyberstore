"""DataTable widget for displaying R2 objects."""

from __future__ import annotations

from datetime import datetime, timezone

import humanize
from textual.message import Message
from textual.widgets import DataTable

from cyberstore.r2_client import R2Object
from cyberstore.utils import format_size, get_file_icon


class ObjectTable(DataTable):
    """A data table for browsing objects in a bucket."""

    class ObjectSelected(Message):
        """Fired when an object row is activated."""

        def __init__(self, obj: R2Object) -> None:
            self.obj = obj
            super().__init__()

    class NavigateUp(Message):
        """Fired when user activates the '..' row."""

    COMPONENT_CLASSES = {"datatable--cursor"}

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._objects: list[R2Object] = []
        self._has_parent = False

    def on_mount(self) -> None:
        self.add_columns("", "Name", "Size", "Type", "Modified")

    def set_objects(self, folders: list[R2Object], objects: list[R2Object], has_parent: bool = False) -> None:
        """Populate the table with folders and objects."""
        self._objects = []
        self._has_parent = has_parent
        self.clear()

        if has_parent:
            self.add_row("⬆️", "..", "", "folder", "", key="__parent__")

        for folder in folders:
            self._objects.append(folder)
            self.add_row(
                "📁",
                folder.name,
                "",
                "folder",
                "",
                key=folder.key,
            )

        for obj in objects:
            self._objects.append(obj)
            icon = get_file_icon(obj.name)
            size = format_size(obj.size)
            modified = ""
            if obj.last_modified:
                try:
                    if isinstance(obj.last_modified, datetime):
                        modified = humanize.naturaltime(datetime.now(timezone.utc) - obj.last_modified)
                    else:
                        modified = str(obj.last_modified)
                except Exception:
                    modified = str(obj.last_modified)
            self.add_row(
                icon,
                obj.name,
                size,
                obj.content_type or "",
                modified,
                key=obj.key,
            )

    def get_selected_object(self) -> R2Object | None:
        """Get the currently highlighted object."""
        if self.cursor_row is None:
            return None
        row_key = self._row_order[self.cursor_row]
        if row_key.value == "__parent__":
            return None
        for obj in self._objects:
            if obj.key == row_key.value:
                return obj
        return None

    def get_selected_objects(self, selected_keys: set[str]) -> list[R2Object]:
        """Get objects matching the selected keys."""
        return [obj for obj in self._objects if obj.key in selected_keys]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row activation."""
        if event.row_key.value == "__parent__":
            self.post_message(self.NavigateUp())
            return
        for obj in self._objects:
            if obj.key == event.row_key.value:
                self.post_message(self.ObjectSelected(obj))
                return
