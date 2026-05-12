from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set

# bot/config.py → repo root (parent of mediabot/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str
    telegram_allowed_users: str  # Comma-separated user IDs

    # ── Services ──────────────────────────────────────────────────────────────
    radarr_url: str = "http://radarr:7878"
    radarr_api_key: str = ""

    sonarr_url: str = "http://sonarr:8989"
    sonarr_api_key: str = ""

    prowlarr_url: str = "http://prowlarr:9696"
    prowlarr_api_key: str = ""

    bazarr_url: str = "http://bazarr:6767"
    bazarr_api_key: str = ""

    qbit_url: str = "http://qbittorrent:8080"
    qbit_user: str = "admin"
    qbit_pass: str = ""

    plex_url: str = "http://plex:32400"
    plex_token: str = ""

    # ── Bot behaviour ─────────────────────────────────────────────────────────
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8222
    log_level: str = "INFO"
    disk_warn_threshold_gb: int = 50
    data_path: str = "/data"
    db_path: str = "/app/data/mediabot.db"

    @property
    def allowed_user_ids(self) -> Set[int]:
        return {int(uid.strip()) for uid in self.telegram_allowed_users.split(",")}

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
