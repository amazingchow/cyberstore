"""First-run setup screen for storage provider credential configuration."""

from __future__ import annotations

from datetime import datetime

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RadioButton, RadioSet, RichLog, Static

from cyberstore.config import PROVIDER_OSS, PROVIDER_R2


class SetupScreen(Screen):
    """Setup wizard for configuring storage provider credentials and CDN settings."""

    DEFAULT_CSS = """
    SetupScreen {
        overflow-y: auto;
    }
    SetupScreen #setup-container {
        width: 70;
        height: auto;
        padding: 2 3;
        align: center top;
        margin: 2 0;
    }
    SetupScreen #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    SetupScreen #subtitle {
        width: 100%;
        content-align: center middle;
        margin-bottom: 2;
        color: $text-muted;
    }
    SetupScreen .field-label {
        margin-top: 1;
    }
    SetupScreen .field-input {
        width: 100%;
    }
    SetupScreen #error-label {
        color: $error;
        height: 1;
        margin-top: 1;
    }
    SetupScreen #save-btn {
        width: 100%;
        margin-top: 2;
    }
    SetupScreen .section-title {
        text-style: bold;
        margin-top: 2;
    }
    SetupScreen #provider-select {
        margin-bottom: 1;
        height: auto;
    }
    SetupScreen #r2-fields {
        height: auto;
    }
    SetupScreen #oss-fields {
        height: auto;
    }
    SetupScreen #log-area {
        height: 10;
        border: solid $border;
        margin-top: 1;
        display: none;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="setup-container"):
            yield Label("⚡ CyberStore Setup", id="title")
            yield Static(
                "Configure your object storage credentials to get started.",
                id="subtitle",
            )

            yield Static("── Storage Provider ──", classes="section-title")
            with RadioSet(id="provider-select"):
                yield RadioButton("Cloudflare R2", id="rb-r2", value=True)
                yield RadioButton("Aliyun OSS", id="rb-oss")

            with Vertical(id="r2-fields"):
                yield Static("── R2 Credentials ──", classes="section-title")
                yield Static("Account ID:", classes="field-label")
                yield Input(
                    placeholder="Your Cloudflare account ID",
                    id="account-id",
                    classes="field-input",
                )
                yield Static("Access Key ID:", classes="field-label")
                yield Input(
                    placeholder="R2 API token access key ID",
                    id="r2-access-key",
                    classes="field-input",
                )
                yield Static("Secret Access Key:", classes="field-label")
                yield Input(
                    placeholder="R2 API token secret access key",
                    id="r2-secret-key",
                    password=True,
                    classes="field-input",
                )

            with Vertical(id="oss-fields"):
                yield Static("── OSS Credentials ──", classes="section-title")
                yield Static("Endpoint:", classes="field-label")
                yield Input(
                    placeholder="e.g., https://oss-cn-hangzhou.aliyuncs.com",
                    id="oss-endpoint",
                    classes="field-input",
                )
                yield Static("Access Key ID:", classes="field-label")
                yield Input(
                    placeholder="Aliyun OSS access key ID",
                    id="oss-access-key",
                    classes="field-input",
                )
                yield Static("Access Key Secret:", classes="field-label")
                yield Input(
                    placeholder="Aliyun OSS access key secret",
                    id="oss-secret-key",
                    password=True,
                    classes="field-input",
                )

            yield Static("── CDN Configuration (Optional) ──", classes="section-title")

            yield Static("Custom Domain:", classes="field-label")
            yield Input(
                placeholder="e.g., cdn.example.com",
                id="cdn-domain",
                classes="field-input",
            )
            yield Static("R2.dev Subdomain:", classes="field-label")
            yield Input(
                placeholder="e.g., pub-xxxxx.r2.dev",
                id="r2-dev-subdomain",
                classes="field-input",
            )

            yield Static("", id="error-label")
            yield Button("Test Connection & Save", variant="success", id="save-btn")

            yield RichLog(id="log-area", highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        config = app.config
        if config.storage_provider == PROVIDER_OSS:
            rs = self.query_one("#provider-select", RadioSet)
            rs.action_select_button(1)
            self._show_oss_fields()
        else:
            self._show_r2_fields()

        self.query_one("#account-id", Input).value = config.r2.account_id
        self.query_one("#r2-access-key", Input).value = config.r2.access_key_id
        self.query_one("#r2-secret-key", Input).value = config.r2.secret_access_key
        self.query_one("#oss-endpoint", Input).value = config.oss.endpoint
        self.query_one("#oss-access-key", Input).value = config.oss.access_key_id
        self.query_one("#oss-secret-key", Input).value = config.oss.access_key_secret
        self.query_one("#cdn-domain", Input).value = config.cdn.custom_domain
        self.query_one("#r2-dev-subdomain", Input).value = config.cdn.r2_dev_subdomain

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "provider-select":
            if event.index == 0:
                self._show_r2_fields()
            else:
                self._show_oss_fields()

    def _show_r2_fields(self) -> None:
        self.query_one("#r2-fields").display = True
        self.query_one("#oss-fields").display = False

    def _show_oss_fields(self) -> None:
        self.query_one("#oss-fields").display = True
        self.query_one("#r2-fields").display = False

    def _selected_provider(self) -> str:
        rs = self.query_one("#provider-select", RadioSet)
        return PROVIDER_OSS if rs.pressed_index == 1 else PROVIDER_R2

    # ── logging helpers ────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info") -> None:
        """Append a timestamped entry to the log panel. Safe to call via call_from_thread."""
        icons = {
            "info": "[dim]●[/dim]",
            "success": "[bold green]✓[/bold green]",
            "error": "[bold red]✗[/bold red]",
            "warn": "[bold yellow]![/bold yellow]",
        }
        icon = icons.get(level, "[dim]●[/dim]")
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            log = self.query_one("#log-area", RichLog)
            # escape() prevents boto3 error strings containing [] or () from breaking Rich markup
            log.write(f"[dim]{ts}[/dim] {icon} {escape(message)}")
        except Exception:
            pass

    def _open_log(self) -> None:
        """Make the log panel visible and clear any previous output. Call from main thread only."""
        log = self.query_one("#log-area", RichLog)
        log.clear()
        log.display = True

    # ── button handler ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_config()

    def _save_config(self) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        provider = self._selected_provider()
        cdn_domain = self.query_one("#cdn-domain", Input).value.strip()
        r2_dev_sub = self.query_one("#r2-dev-subdomain", Input).value.strip()

        if provider == PROVIDER_R2:
            account_id = self.query_one("#account-id", Input).value.strip()
            access_key = self.query_one("#r2-access-key", Input).value.strip()
            secret_key = self.query_one("#r2-secret-key", Input).value.strip()
            if not account_id or not access_key or not secret_key:
                self.query_one("#error-label", Static).update("All R2 credential fields are required")
                return
        else:
            oss_endpoint = self.query_one("#oss-endpoint", Input).value.strip()
            oss_access_key = self.query_one("#oss-access-key", Input).value.strip()
            oss_secret_key = self.query_one("#oss-secret-key", Input).value.strip()
            if not oss_endpoint or not oss_access_key or not oss_secret_key:
                self.query_one("#error-label", Static).update("All OSS credential fields are required")
                return

        self.query_one("#error-label", Static).update("")
        self.query_one("#save-btn", Button).disabled = True

        # Open log panel on the main thread before spawning the worker thread.
        # Setting widget.display must happen here — doing it inside call_from_thread
        # is unreliable because Textual may defer the layout update.
        self._open_log()
        self._log("Preparing configuration...", "info")

        config = app.config
        config.storage_provider = provider

        if provider == PROVIDER_R2:
            config.r2.account_id = self.query_one("#account-id", Input).value.strip()
            config.r2.access_key_id = self.query_one("#r2-access-key", Input).value.strip()
            config.r2.secret_access_key = self.query_one("#r2-secret-key", Input).value.strip()
            self._log("Provider : Cloudflare R2", "info")
            self._log(f"Endpoint : {config.r2.endpoint_url}", "info")
        else:
            config.oss.endpoint = self.query_one("#oss-endpoint", Input).value.strip()
            config.oss.access_key_id = self.query_one("#oss-access-key", Input).value.strip()
            config.oss.access_key_secret = self.query_one("#oss-secret-key", Input).value.strip()
            self._log("Provider : Aliyun OSS", "info")
            self._log(f"Endpoint : {config.oss.endpoint}", "info")

        config.cdn.custom_domain = cdn_domain
        config.cdn.r2_dev_subdomain = r2_dev_sub

        app.rebuild_storage_client()
        self._log("Connecting... (timeout 10 s)", "info")

        import threading

        # Capture a direct reference so the closure doesn't need to re-resolve app.storage_client
        storage_client = app.storage_client

        def test_and_save() -> None:
            try:
                success, msg = storage_client.test_connection_detail()
                # Use app.call_from_thread (more reliable than self.call_from_thread)
                # to schedule UI updates back onto the event loop.
                app.call_from_thread(self._log, msg, "success" if success else "error")
                app.call_from_thread(self._on_test_result, success)
            except Exception as e:
                err = f"Unhandled error: {type(e).__name__}: {e}"
                app.call_from_thread(self._log, err, "error")
                app.call_from_thread(self._on_test_result, False)

        threading.Thread(target=test_and_save, daemon=True).start()

    def _on_test_result(self, success: bool) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        self.query_one("#save-btn", Button).disabled = False

        if success:
            app.config.save()
            self._log("Configuration saved.", "success")
            self.notify("Configuration saved!", severity="information")
            app.switch_to_main()
        else:
            self._log("Check your credentials and try again.", "warn")
            self.query_one("#error-label", Static).update("Connection failed. See log below for details.")
