"""Configuration management using TOML files."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".config" / "cyberstore"
CONFIG_FILE = CONFIG_DIR / "config.toml"

PROVIDER_R2 = "r2"
PROVIDER_OSS = "oss"


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
class OSSConfig:
    """Aliyun OSS credentials."""

    endpoint: str = ""
    bucket: str = ""
    access_key_id: str = ""
    access_key_secret: str = ""

    def is_valid(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key_id and self.access_key_secret)

    def region_name(self) -> str:
        """Derive region from endpoint, e.g. oss-cn-shenzhen from https://oss-cn-shenzhen.aliyuncs.com."""
        endpoint = self.endpoint
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]
        host = endpoint.split("/")[0]
        parts = host.split(".")
        for part in parts:
            if part.startswith("oss-"):
                return part
        return parts[0] if parts else "oss-cn-hangzhou"


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

    theme: str = "textual-dark"
    download_path: str = str(Path.home() / "Downloads")
    presigned_expiry: int = 3600  # seconds


@dataclass
class AppConfig:
    """Top-level application configuration."""

    storage_provider: str = PROVIDER_R2
    r2: R2Config = field(default_factory=R2Config)
    oss: OSSConfig = field(default_factory=OSSConfig)
    cdn: CDNConfig = field(default_factory=CDNConfig)
    preferences: Preferences = field(default_factory=Preferences)

    def is_configured(self) -> bool:
        if self.storage_provider == PROVIDER_OSS:
            return self.oss.is_valid()
        return self.r2.is_valid()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "storage_provider": self.storage_provider,
            "r2": {
                "account_id": self.r2.account_id,
                "access_key_id": self.r2.access_key_id,
                "secret_access_key": self.r2.secret_access_key,
            },
            "oss": {
                "endpoint": self.oss.endpoint,
                "bucket": self.oss.bucket,
                "access_key_id": self.oss.access_key_id,
                "access_key_secret": self.oss.access_key_secret,
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

        config.storage_provider = data.get("storage_provider", PROVIDER_R2)
        if r2 := data.get("r2"):
            config.r2 = R2Config(
                account_id=r2.get("account_id", ""),
                access_key_id=r2.get("access_key_id", ""),
                secret_access_key=r2.get("secret_access_key", ""),
            )
        if oss := data.get("oss"):
            config.oss = OSSConfig(
                endpoint=oss.get("endpoint", ""),
                bucket=oss.get("bucket", ""),
                access_key_id=oss.get("access_key_id", ""),
                access_key_secret=oss.get("access_key_secret", ""),
            )
        if cdn := data.get("cdn"):
            config.cdn = CDNConfig(
                custom_domain=cdn.get("custom_domain", ""),
                r2_dev_subdomain=cdn.get("r2_dev_subdomain", ""),
            )
        if prefs := data.get("preferences"):
            config.preferences = Preferences(
                theme=prefs.get("theme", "textual-dark"),
                download_path=prefs.get("download_path", str(Path.home() / "Downloads")),
                presigned_expiry=prefs.get("presigned_expiry", 3600),
            )
        return config
