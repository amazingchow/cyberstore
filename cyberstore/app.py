"""CyberStore - Main application class."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from cyberstore.config import PROVIDER_OSS, AppConfig
from cyberstore.oss_client import OSSClient
from cyberstore.r2_client import R2Client

CSS_DIR = Path(__file__).parent / "styles"

THEMES = [
    "nord",
    "gruvbox",
    "tokyo-night",
    "textual-dark",
    "solarized-light",
    "atom-one-dark",
    "atom-one-light",
]


class CyberStoreApp(App):
    """Object storage TUI client (Cloudflare R2 / Aliyun OSS)."""

    TITLE = "CyberStore"
    SUB_TITLE = "Object Storage Manager"

    CSS_PATH = [
        CSS_DIR / "app.tcss",
        CSS_DIR / "modals.tcss",
    ]

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+t", "cycle_theme", "Theme"),
        ("ctrl+p", "command_palette", "Commands"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = AppConfig.load()
        self.storage_client = self._build_client()

    def _build_client(self) -> R2Client | OSSClient:
        if self.config.storage_provider == PROVIDER_OSS:
            return OSSClient(self.config)
        return R2Client(self.config)

    def rebuild_storage_client(self) -> None:
        """Rebuild the storage client after a provider/credential change."""
        self.storage_client = self._build_client()

    @property
    def r2_client(self) -> R2Client | OSSClient:
        """Backward-compatible alias for storage_client."""
        return self.storage_client

    def on_mount(self) -> None:
        saved = self.config.preferences.theme
        self.theme = saved if saved in THEMES else "textual-dark"
        if self.config.is_configured():
            self.call_after_refresh(self._push_main)
        else:
            self.call_after_refresh(self._push_setup)

    def _push_main(self) -> None:
        from cyberstore.screens.main_screen import MainScreen

        self.push_screen(MainScreen())

    def _push_setup(self) -> None:
        from cyberstore.screens.setup_screen import SetupScreen

        self.push_screen(SetupScreen())

    def switch_to_main(self) -> None:
        """Called from setup screen after credentials are saved."""
        from cyberstore.screens.main_screen import MainScreen

        self.switch_screen(MainScreen())

    def action_cycle_theme(self) -> None:
        try:
            idx = THEMES.index(self.theme)
        except ValueError:
            idx = -1
        next_theme = THEMES[(idx + 1) % len(THEMES)]
        self.theme = next_theme
        self.config.preferences.theme = next_theme
        self.config.save()
