"""Configuration management using TOML files."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".config" / "cyberstore"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class R2Config:
    """Cloudflare R2 credentials."""

    account_id: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def is_valid(self) -> bool:
        return bool(self.account_id and self.access_key_id and self.secret_access_key)


@dataclass
class CDNConfig:
    """CDN configuration for public URLs."""

    custom_domain: str = ""
    r2_dev_subdomain: str = ""

    def get_base_url(self) -> str | None:
        if self.custom_domain:
            domain = self.custom_domain.rstrip("/")
            if not domain.startswith("http"):
                domain = f"https://{domain}"
            return domain
        if self.r2_dev_subdomain:
            sub = self.r2_dev_subdomain.rstrip("/")
            if not sub.startswith("http"):
                sub = f"https://{sub}"
            return sub
        return None


@dataclass
class Preferences:
    """User preferences."""

    theme: str = "dark"
    download_path: str = str(Path.home() / "Downloads")
    presigned_expiry: int = 3600  # seconds


@dataclass
class AppConfig:
    """Top-level application configuration."""

    r2: R2Config = field(default_factory=R2Config)
    cdn: CDNConfig = field(default_factory=CDNConfig)
    preferences: Preferences = field(default_factory=Preferences)

    def is_configured(self) -> bool:
        return self.r2.is_valid()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "r2": {
                "account_id": self.r2.account_id,
                "access_key_id": self.r2.access_key_id,
                "secret_access_key": self.r2.secret_access_key,
            },
            "cdn": {
                "custom_domain": self.cdn.custom_domain,
                "r2_dev_subdomain": self.cdn.r2_dev_subdomain,
            },
            "preferences": {
                "theme": self.preferences.theme,
                "download_path": self.preferences.download_path,
                "presigned_expiry": self.preferences.presigned_expiry,
            },
        }
        CONFIG_FILE.write_bytes(tomli_w.dumps(data).encode())

    @classmethod
    def load(cls) -> AppConfig:
        config = cls()
        if not CONFIG_FILE.exists():
            return config
        try:
            data = tomllib.loads(CONFIG_FILE.read_text())
        except Exception:
            return config

        if r2 := data.get("r2"):
            config.r2 = R2Config(
                account_id=r2.get("account_id", ""),
                access_key_id=r2.get("access_key_id", ""),
                secret_access_key=r2.get("secret_access_key", ""),
            )
        if cdn := data.get("cdn"):
            config.cdn = CDNConfig(
                custom_domain=cdn.get("custom_domain", ""),
                r2_dev_subdomain=cdn.get("r2_dev_subdomain", ""),
            )
        if prefs := data.get("preferences"):
            config.preferences = Preferences(
                theme=prefs.get("theme", "dark"),
                download_path=prefs.get("download_path", str(Path.home() / "Downloads")),
                presigned_expiry=prefs.get("presigned_expiry", 3600),
            )
        return config
