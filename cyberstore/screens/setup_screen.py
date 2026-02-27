"""First-run setup screen for R2 credential configuration."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static


class SetupScreen(Screen):
    """Setup wizard for configuring R2 credentials and CDN settings."""

    DEFAULT_CSS = """
    SetupScreen {
        align: center middle;
    }
    SetupScreen #setup-container {
        width: 70;
        height: auto;
        padding: 2 3;
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
        color: red;
        height: 1;
        margin-top: 1;
    }
    SetupScreen #status-label {
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
    """

    BINDINGS = [
        ("escape", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="setup-container"):
            yield Label("⚡ CyberStore Setup", id="title")
            yield Static(
                "Configure your Cloudflare R2 credentials to get started.",
                id="subtitle",
            )

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
                id="access-key",
                classes="field-input",
            )
            yield Static("Secret Access Key:", classes="field-label")
            yield Input(
                placeholder="R2 API token secret access key",
                id="secret-key",
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
            yield Static("", id="status-label")
            yield Button("Test Connection & Save", variant="success", id="save-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_config()

    def _save_config(self) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        account_id = self.query_one("#account-id", Input).value.strip()
        access_key = self.query_one("#access-key", Input).value.strip()
        secret_key = self.query_one("#secret-key", Input).value.strip()
        cdn_domain = self.query_one("#cdn-domain", Input).value.strip()
        r2_dev_sub = self.query_one("#r2-dev-subdomain", Input).value.strip()

        if not account_id or not access_key or not secret_key:
            self.query_one("#error-label", Static).update("All R2 credential fields are required")
            return

        self.query_one("#error-label", Static).update("")
        self.query_one("#status-label", Static).update("Testing connection...")
        self.query_one("#save-btn", Button).disabled = True

        config = app.config
        config.r2.account_id = account_id
        config.r2.access_key_id = access_key
        config.r2.secret_access_key = secret_key
        config.cdn.custom_domain = cdn_domain
        config.cdn.r2_dev_subdomain = r2_dev_sub

        app.r2_client.reset_client()

        import threading

        def test_and_save() -> None:
            success = app.r2_client.test_connection()
            self.call_from_thread(self._on_test_result, success)

        threading.Thread(target=test_and_save, daemon=True).start()

    def _on_test_result(self, success: bool) -> None:
        from cyberstore.app import CyberStoreApp

        app = self.app
        if not isinstance(app, CyberStoreApp):
            return

        self.query_one("#save-btn", Button).disabled = False

        if success:
            app.config.save()
            self.query_one("#status-label", Static).update("Connection successful!")
            self.notify("Configuration saved!", severity="information")
            app.switch_to_main()
        else:
            self.query_one("#error-label", Static).update("Connection failed. Please check your credentials.")
            self.query_one("#status-label", Static).update("")
