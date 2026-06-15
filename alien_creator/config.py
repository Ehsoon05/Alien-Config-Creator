from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _admin_ids(value: str) -> frozenset[int]:
    ids = set()
    for item in value.split(","):
        item = item.strip()
        if item.isdigit():
            ids.add(int(item))
    return frozenset(ids)


def _as_bool(value: str, default: bool = True) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    marzban_url: str
    marzban_username: str
    marzban_password: str
    easy_panel_url: str
    easy_panel_username: str
    easy_panel_password: str
    easy_panel_group_ids: tuple[int, ...]
    database_path: Path
    log_level: str
    verify_ssl: bool

    @classmethod
    def from_env(cls) -> "Config":
        config = cls(
            bot_token=os.getenv("BOT_TOKEN", "").strip(),
            admin_ids=_admin_ids(os.getenv("ADMIN_IDS", "")),
            marzban_url=os.getenv("MARZBAN_URL", "").strip().rstrip("/"),
            marzban_username=os.getenv("MARZBAN_USERNAME", "").strip(),
            marzban_password=os.getenv("MARZBAN_PASSWORD", ""),
            easy_panel_url=os.getenv("EASY_PANEL_URL", "").strip().rstrip("/"),
            easy_panel_username=os.getenv("EASY_PANEL_USERNAME", "").strip(),
            easy_panel_password=os.getenv("EASY_PANEL_PASSWORD", ""),
            easy_panel_group_ids=tuple(
                int(item.strip())
                for item in os.getenv("EASY_PANEL_GROUP_IDS", "1").split(",")
                if item.strip().isdigit()
            ),
            database_path=Path(os.getenv("DATABASE_PATH", "data/settings.db")),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            verify_ssl=_as_bool(os.getenv("VERIFY_SSL", "true")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.admin_ids:
            missing.append("ADMIN_IDS")
        if not self.marzban_url:
            missing.append("MARZBAN_URL")
        if not self.marzban_username:
            missing.append("MARZBAN_USERNAME")
        if not self.marzban_password:
            missing.append("MARZBAN_PASSWORD")
        if not self.easy_panel_url:
            missing.append("EASY_PANEL_URL")
        if not self.easy_panel_username:
            missing.append("EASY_PANEL_USERNAME")
        if not self.easy_panel_password:
            missing.append("EASY_PANEL_PASSWORD")
        if not self.easy_panel_group_ids:
            missing.append("EASY_PANEL_GROUP_IDS")
        if missing:
            raise RuntimeError(f"Missing required settings: {', '.join(missing)}")
