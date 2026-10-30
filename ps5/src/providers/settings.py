"""Load server-side provider settings from the environment. Never expose secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _is_blank_env(value: str) -> bool:
    return value.strip().strip('"').strip("'").lower() in {
        "",
        "0",
        "none",
        "null",
        "changeme",
        "your_key_here",
        "your_api_key",
    }


def load_dotenv_file(path: Path | None = None) -> None:
    if os.environ.get("PS5_DISABLE_PROVIDER_DOTENV", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    env_path = path or (ROOT / ".env")
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception:
        pass
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        name = key.strip()
        parsed = value.strip().strip('"').strip("'")
        if name not in os.environ or _is_blank_env(os.environ.get(name, "")):
            os.environ[name] = parsed


load_dotenv_file()


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _clean_secret(name: str) -> str:
    raw = os.environ.get(name, "").strip().strip('"').strip("'")
    if raw.lower() in {"", "0", "none", "null", "changeme", "your_key_here", "your_api_key"}:
        return ""
    return raw


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class ProviderSettings:
    digikey_client_id: str
    digikey_client_secret: str
    digikey_refresh_token: str
    digikey_account_id: str
    digikey_customer_id: str
    digikey_api_base: str
    digikey_environment: str
    nexar_client_id: str
    nexar_client_secret: str
    nexar_access_token: str
    nexar_scope: str
    mouser_api_key: str
    mouser_api_base: str
    cache_ttl_seconds: int
    batch_size: int
    request_delay_ms: int
    max_retries: int
    backoff_factor: float
    target_region: str
    target_currency: str

    @property
    def digikey_configured(self) -> bool:
        return bool(self.digikey_client_id and self.digikey_client_secret)

    @property
    def nexar_configured(self) -> bool:
        return bool(self.nexar_access_token) or bool(self.nexar_client_id and self.nexar_client_secret)

    @property
    def mouser_configured(self) -> bool:
        return bool(self.mouser_api_key)


def get_settings() -> ProviderSettings:
    load_dotenv_file()
    env_str = os.environ.get("DIGIKEY_ENVIRONMENT", "").strip().lower()
    sandbox = (env_str == "sandbox") or _bool("DIGIKEY_SANDBOX", False)
    digikey_env = "sandbox" if sandbox else "production"
    default_base = "https://sandbox-api.digikey.com" if sandbox else "https://api.digikey.com"
    return ProviderSettings(
        digikey_client_id=_clean_secret("DIGIKEY_CLIENT_ID"),
        digikey_client_secret=_clean_secret("DIGIKEY_CLIENT_SECRET"),
        digikey_refresh_token=_clean_secret("DIGIKEY_REFRESH_TOKEN"),
        digikey_account_id=_clean_secret("DIGIKEY_ACCOUNT_ID") or _clean_secret("DIGIKEY_CUSTOMER_ID"),
        digikey_customer_id=_clean_secret("DIGIKEY_CUSTOMER_ID"),
        digikey_api_base=os.environ.get("DIGIKEY_API_BASE", default_base).strip() or default_base,
        digikey_environment=digikey_env,
        nexar_client_id=_clean_secret("NEXAR_CLIENT_ID"),
        nexar_client_secret=_clean_secret("NEXAR_CLIENT_SECRET"),
        nexar_access_token=_clean_secret("NEXAR_ACCESS_TOKEN"),
        nexar_scope=os.environ.get("NEXAR_SCOPE", "supply.domain").strip() or "supply.domain",
        mouser_api_key=_clean_secret("MOUSER_API_KEY") or _clean_secret("MOUSER_SEARCH_API_KEY"),
        mouser_api_base=(os.environ.get("MOUSER_API_BASE", "https://api.mouser.com/api/v1").strip() or "https://api.mouser.com/api/v1").rstrip("/"),
        cache_ttl_seconds=_int("API_CACHE_TTL_SECONDS", 86400),
        batch_size=max(1, _int("API_BATCH_SIZE", 50)),
        request_delay_ms=max(0, _int("API_REQUEST_DELAY_MS", 250)),
        max_retries=max(0, _int("API_MAX_RETRIES", 3)),
        backoff_factor=max(1.0, _float("API_BACKOFF_FACTOR", 2.0)),
        target_region=(os.environ.get("TARGET_REGION", "IN").strip() or "IN").upper(),
        target_currency=(os.environ.get("TARGET_CURRENCY", "INR").strip() or "INR").upper(),
    )
