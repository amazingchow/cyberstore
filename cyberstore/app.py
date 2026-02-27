"""CyberStore - Main application class."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from cyberstore.config import AppConfig
from cyberstore.r2_client import R2Client

CSS_DIR = Path(__file__).parent / "styles"


class CyberStoreApp(App):
    """Cyberpunk-themed Cloudflare R2 TUI client."""

    TITLE = "CyberStore"
    SUB_TITLE = "Cloudflare R2 Manager"

    CSS_PATH = [
        CSS_DIR / "app.tcss",
        CSS_DIR / "modals.tcss",
    ]

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+t", "toggle_dark", "Theme"),
        ("ctrl+p", "command_palette", "Commands"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = AppConfig.load()
        self.r2_client = R2Client(self.config)

    def on_mount(self) -> None:
        if self.config.preferences.theme == "light":
            self.theme = "textual-light"
        if self.config.is_configured():
            self.switch_to_main()
        else:
            self._push_setup()

    def _push_setup(self) -> None:
        from cyberstore.screens.setup_screen import SetupScreen

        self.push_screen(SetupScreen())

    def switch_to_main(self) -> None:
        from cyberstore.screens.main_screen import MainScreen

        self.switch_screen(MainScreen())

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark
        self.config.preferences.theme = "dark" if self.dark else "light"
        self.config.save()
