"""Primary browser screen with bucket tree and object table."""

from __future__ import annotations

import threading

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from cyberstore.r2_client import R2Object
from cyberstore.utils import format_size
from cyberstore.widgets.breadcrumb import Breadcrumb
from cyberstore.widgets.bucket_tree import BucketTree
from cyberstore.widgets.object_table import ObjectTable
from cyberstore.widgets.search_bar import SearchBar
from cyberstore.widgets.status_bar import StatusBar

try:
    import pyperclip

    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class MainScreen(Screen):
    """The main browser screen showing buckets and objects."""

    DEFAULT_CSS = """
    MainScreen {
        layout: vertical;
    }
    MainScreen #content {
        height: 1fr;
    }
    MainScreen #sidebar {
        width: 28;
        height: 100%;
    }
    MainScreen #main-panel {
        width: 1fr;
        height: 100%;
    }
    MainScreen #search-bar {
        dock: top;
        height: 3;
        padding: 0 1;
    }
    MainScreen #breadcrumb {
        height: 1;
    }
    MainScreen #object-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("u", "upload", "Upload"),
        ("d", "download", "Download"),
        ("x", "delete", "Delete"),
        ("l", "link", "Link"),
        ("i", "info", "Info"),
        ("c", "copy_key", "Copy Key"),
        ("r", "refresh", "Refresh"),
        ("slash", "focus_search", "Search"),
        ("backspace", "go_up", "Go Up"),
        ("space", "toggle_select", "Select"),
        ("n", "new_bucket", "New Bucket"),
        ("f", "new_folder", "New Folder"),
        ("escape", "clear_search", "Clear"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_bucket: str = ""
        self._current_prefix: str = ""
        self._selected_keys: set[str] = set()
        self._all_folders: list[R2Object] = []
        self._all_objects: list[R2Object] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield SearchBar(id="search-bar")
        with Horizontal(id="content"):
            yield BucketTree(id="sidebar")
            with Vertical(id="main-panel"):
                yield Breadcrumb(id="breadcrumb")
                yield ObjectTable(id="object-table")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._load_buckets()

    def _get_app(self):
        from cyberstore.app import CyberStoreApp

        app = self.app
        if isinstance(app, CyberStoreApp):
            return app
        return None

    def _load_buckets(self) -> None:
        app = self._get_app()
        if not app:
            return

        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.set_connected(True)

        from cyberstore.config import PROVIDER_OSS

        if app.config.storage_provider == PROVIDER_OSS:
            self._on_buckets_loaded([app.config.oss.bucket])
            return

        def do_load():
            try:
                buckets = app.r2_client.list_buckets()
                names = [b.name for b in buckets]
                self.app.call_from_thread(self._on_buckets_loaded, names)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error loading buckets: {e}", severity="error")

        threading.Thread(target=do_load, daemon=True).start()

    def _on_buckets_loaded(self, names: list[str]) -> None:
        tree = self.query_one("#sidebar", BucketTree)
        tree.set_buckets(names)
        if len(names) == 1:
            self._current_bucket = names[0]
            self._current_prefix = ""
            self._selected_keys.clear()
            self._load_objects()

    def on_bucket_tree_bucket_selected(self, event: BucketTree.BucketSelected) -> None:
        self._current_bucket = event.bucket_name
        self._current_prefix = ""
        self._selected_keys.clear()
        self._load_objects()

    def _load_objects(self) -> None:
        app = self._get_app()
        if not app or not self._current_bucket:
            return

        def do_load():
            try:
                result = app.r2_client.list_objects(self._current_bucket, self._current_prefix)
                self.app.call_from_thread(self._on_objects_loaded, result.folders, result.objects)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")

        threading.Thread(target=do_load, daemon=True).start()

    def _on_objects_loaded(self, folders: list[R2Object], objects: list[R2Object]) -> None:
        self._all_folders = folders
        self._all_objects = objects
        self._selected_keys.clear()

        breadcrumb = self.query_one("#breadcrumb", Breadcrumb)
        breadcrumb.set_path(self._current_bucket, self._current_prefix)

        table = self.query_one("#object-table", ObjectTable)
        has_parent = bool(self._current_prefix)
        table.set_objects(folders, objects, has_parent=has_parent)

        total_size = sum(o.size for o in objects)
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.set_bucket(self._current_bucket)
        status_bar.set_object_info(len(folders) + len(objects), format_size(total_size))

        search = self.query_one("#search-bar", SearchBar)
        if search.value:
            self._filter_objects(search.value)

    def on_object_table_object_selected(self, event: ObjectTable.ObjectSelected) -> None:
        if event.obj.is_folder:
            self._current_prefix = event.obj.key
            self._load_objects()

    def on_object_table_navigate_up(self, event: ObjectTable.NavigateUp) -> None:
        self._go_up()

    def _go_up(self) -> None:
        if self._current_prefix:
            parts = self._current_prefix.rstrip("/").split("/")
            if len(parts) > 1:
                self._current_prefix = "/".join(parts[:-1]) + "/"
            else:
                self._current_prefix = ""
            self._load_objects()

    def on_search_bar_search_changed(self, event: SearchBar.SearchChanged) -> None:
        self._filter_objects(event.query)

    def _filter_objects(self, query: str) -> None:
        table = self.query_one("#object-table", ObjectTable)
        if not query:
            has_parent = bool(self._current_prefix)
            table.set_objects(self._all_folders, self._all_objects, has_parent=has_parent)
            return

        q = query.lower()
        filtered_folders = [f for f in self._all_folders if q in f.name.lower()]
        filtered_objects = [o for o in self._all_objects if q in o.name.lower()]
        has_parent = bool(self._current_prefix)
        table.set_objects(filtered_folders, filtered_objects, has_parent=has_parent)

    def action_upload(self) -> None:
        if not self._current_bucket:
            self.notify("Select a bucket first", severity="warning")
            return

        from cyberstore.screens.upload_screen import UploadScreen

        def on_upload_result(result: str | None) -> None:
            if result:
                self._load_objects()

        self.app.push_screen(
            UploadScreen(self._current_bucket, self._current_prefix),
            callback=on_upload_result,
        )

    def action_download(self) -> None:
        if not self._current_bucket:
            self.notify("Select a bucket first", severity="warning")
            return

        table = self.query_one("#object-table", ObjectTable)
        obj = table.get_selected_object()
        if not obj or obj.is_folder:
            self.notify("Select a file to download", severity="warning")
            return

        app = self._get_app()
        download_dir = app.config.preferences.download_path if app else ""

        from cyberstore.screens.download_screen import DownloadScreen

        self.app.push_screen(DownloadScreen(self._current_bucket, obj.key, obj.size, download_dir))

    def action_delete(self) -> None:
        if not self._current_bucket:
            self.notify("Select a bucket first", severity="warning")
            return

        table = self.query_one("#object-table", ObjectTable)

        if self._selected_keys:
            keys = list(self._selected_keys)
        else:
            obj = table.get_selected_object()
            if not obj:
                self.notify("Select an object to delete", severity="warning")
                return
            keys = [obj.key]

        from cyberstore.screens.delete_confirm import DeleteConfirmScreen

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._do_delete(keys)

        self.app.push_screen(DeleteConfirmScreen(keys), callback=on_confirm)

    def _do_delete(self, keys: list[str]) -> None:
        app = self._get_app()
        if not app:
            return

        def do_delete():
            try:
                app.r2_client.delete_objects(self._current_bucket, keys)
                self.app.call_from_thread(self._on_delete_done, len(keys))
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Delete error: {e}", severity="error")

        threading.Thread(target=do_delete, daemon=True).start()

    def _on_delete_done(self, count: int) -> None:
        self._selected_keys.clear()
        self.notify(f"Deleted {count} object{'s' if count > 1 else ''}")
        self._load_objects()

    def action_link(self) -> None:
        if not self._current_bucket:
            return

        table = self.query_one("#object-table", ObjectTable)
        obj = table.get_selected_object()
        if not obj or obj.is_folder:
            self.notify("Select a file to get links", severity="warning")
            return

        app = self._get_app()
        if not app:
            return

        def do_get_links():
            try:
                cdn_url = app.r2_client.get_cdn_url(self._current_bucket, obj.key)
                presigned_url = app.r2_client.generate_presigned_url(self._current_bucket, obj.key)
                self.app.call_from_thread(self._show_link_screen, obj.key, cdn_url, presigned_url)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")

        threading.Thread(target=do_get_links, daemon=True).start()

    def _show_link_screen(self, key: str, cdn_url: str | None, presigned_url: str | None) -> None:
        from cyberstore.screens.link_screen import LinkScreen

        self.app.push_screen(LinkScreen(key, cdn_url, presigned_url))

    def action_info(self) -> None:
        if not self._current_bucket:
            return

        table = self.query_one("#object-table", ObjectTable)
        obj = table.get_selected_object()
        if not obj or obj.is_folder:
            self.notify("Select a file to view info", severity="warning")
            return

        app = self._get_app()
        if not app:
            return

        def do_head():
            try:
                metadata = app.r2_client.head_object(self._current_bucket, obj.key)
                self.app.call_from_thread(self._show_info_screen, metadata)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")

        threading.Thread(target=do_head, daemon=True).start()

    def _show_info_screen(self, metadata: dict) -> None:
        from cyberstore.screens.object_info_screen import ObjectInfoScreen

        self.app.push_screen(ObjectInfoScreen(metadata))

    def action_copy_key(self) -> None:
        table = self.query_one("#object-table", ObjectTable)
        obj = table.get_selected_object()
        if not obj:
            return

        if HAS_PYPERCLIP:
            try:
                pyperclip.copy(obj.key)
                self.notify(f"Copied: {obj.key}")
                return
            except Exception:
                pass
        self.notify("Could not copy to clipboard", severity="warning")

    def action_refresh(self) -> None:
        if self._current_bucket:
            self._load_objects()
        self._load_buckets()

    def action_focus_search(self) -> None:
        self.query_one("#search-bar", SearchBar).focus()

    def action_go_up(self) -> None:
        self._go_up()

    def action_toggle_select(self) -> None:
        table = self.query_one("#object-table", ObjectTable)
        obj = table.get_selected_object()
        if not obj:
            return
        if obj.key in self._selected_keys:
            self._selected_keys.discard(obj.key)
        else:
            self._selected_keys.add(obj.key)

    def action_new_bucket(self) -> None:
        app = self._get_app()
        from cyberstore.config import PROVIDER_OSS

        if app and app.config.storage_provider == PROVIDER_OSS:
            self.notify("Bucket is pre-configured via OSS endpoint", severity="warning")
            return

        from cyberstore.screens.bucket_create_screen import BucketCreateScreen

        def on_result(name: str | None) -> None:
            if name:
                self._create_bucket(name)

        self.app.push_screen(BucketCreateScreen(), callback=on_result)

    def _create_bucket(self, name: str) -> None:
        app = self._get_app()
        if not app:
            return

        def do_create():
            try:
                app.r2_client.create_bucket(name)
                self.app.call_from_thread(self._on_bucket_created, name)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")

        threading.Thread(target=do_create, daemon=True).start()

    def _on_bucket_created(self, name: str) -> None:
        self.notify(f"Bucket created: {name}")
        self._load_buckets()

    def action_new_folder(self) -> None:
        if not self._current_bucket:
            self.notify("Select a bucket first", severity="warning")
            return

        from cyberstore.screens.folder_create_screen import FolderCreateScreen

        def on_result(folder_name: str | None) -> None:
            if folder_name:
                self._create_folder(folder_name)

        self.app.push_screen(
            FolderCreateScreen(self._current_bucket, self._current_prefix),
            callback=on_result,
        )

    def _create_folder(self, folder_name: str) -> None:
        app = self._get_app()
        if not app:
            return

        def do_create():
            try:
                key = app.r2_client.create_folder(self._current_bucket, self._current_prefix, folder_name)
                self.app.call_from_thread(self._on_folder_created, key)
            except Exception as e:
                self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")

        threading.Thread(target=do_create, daemon=True).start()

    def _on_folder_created(self, key: str) -> None:
        folder_display = key.rstrip("/").split("/")[-1]
        self.notify(f"Folder created: {folder_display}/")
        self._load_objects()

    def action_clear_search(self) -> None:
        search = self.query_one("#search-bar", SearchBar)
        if search.value:
            search.value = ""
            self._filter_objects("")
