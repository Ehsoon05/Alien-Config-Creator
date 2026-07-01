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


def _as_int(value: str, default: int) -> int:
    try:
        return int(value.strip())
    except (AttributeError, ValueError):
        return default


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
    easy_panel_hwid_limit: int | None
    mexico_hajmi_panel_url: str
    mexico_hajmi_panel_username: str
    mexico_hajmi_panel_password: str
    mexico_hajmi_panel_group_ids: tuple[int, ...]
    mexico_hajmi_panel_hwid_limit: int | None
    mexico_namahdod_panel_url: str
    mexico_namahdod_panel_username: str
    mexico_namahdod_panel_password: str
    mexico_namahdod_panel_group_ids: tuple[int, ...]
    mexico_namahdod_panel_hwid_limit: int | None
    database_path: Path
    log_level: str
    verify_ssl: bool
    subscription_public_base_url: str
    subscription_panel_sync_url: str
    subscription_panel_sync_token: str

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
            easy_panel_hwid_limit=(
                _as_int(os.getenv("EASY_PANEL_HWID_LIMIT", ""), 2)
                if os.getenv("EASY_PANEL_HWID_LIMIT", "").strip()
                else None
            ),
            mexico_hajmi_panel_url=os.getenv("MEXICO_HAJMI_PANEL_URL", "").strip().rstrip("/"),
            mexico_hajmi_panel_username=os.getenv("MEXICO_HAJMI_PANEL_USERNAME", "").strip(),
            mexico_hajmi_panel_password=os.getenv("MEXICO_HAJMI_PANEL_PASSWORD", ""),
            mexico_hajmi_panel_group_ids=tuple(
                int(item.strip())
                for item in os.getenv("MEXICO_HAJMI_PANEL_GROUP_IDS", "1").split(",")
                if item.strip().isdigit()
            ),
            mexico_hajmi_panel_hwid_limit=(
                _as_int(os.getenv("MEXICO_HAJMI_PANEL_HWID_LIMIT", ""), 2)
                if os.getenv("MEXICO_HAJMI_PANEL_HWID_LIMIT", "").strip()
                else None
            ),
            mexico_namahdod_panel_url=os.getenv("MEXICO_NAMAHDOD_PANEL_URL", "").strip().rstrip("/"),
            mexico_namahdod_panel_username=os.getenv("MEXICO_NAMAHDOD_PANEL_USERNAME", "").strip(),
            mexico_namahdod_panel_password=os.getenv("MEXICO_NAMAHDOD_PANEL_PASSWORD", ""),
            mexico_namahdod_panel_group_ids=tuple(
                int(item.strip())
                for item in os.getenv("MEXICO_NAMAHDOD_PANEL_GROUP_IDS", "1").split(",")
                if item.strip().isdigit()
            ),
            mexico_namahdod_panel_hwid_limit=(
                _as_int(os.getenv("MEXICO_NAMAHDOD_PANEL_HWID_LIMIT", ""), 2)
                if os.getenv("MEXICO_NAMAHDOD_PANEL_HWID_LIMIT", "").strip()
                else None
            ),
            database_path=Path(os.getenv("DATABASE_PATH", "data/settings.db")),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            verify_ssl=_as_bool(os.getenv("VERIFY_SSL", "true")),
            subscription_public_base_url=os.getenv("SUBSCRIPTION_PUBLIC_BASE_URL", "").strip().rstrip("/"),
            subscription_panel_sync_url=os.getenv("SUBSCRIPTION_PANEL_SYNC_URL", "").strip(),
            subscription_panel_sync_token=os.getenv("SUBSCRIPTION_PANEL_SYNC_TOKEN", "").strip(),
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
        mexico_panels = [
            (
                "MEXICO_HAJMI",
                self.mexico_hajmi_panel_url,
                self.mexico_hajmi_panel_username,
                self.mexico_hajmi_panel_password,
                self.mexico_hajmi_panel_group_ids,
            ),
            (
                "MEXICO_NAMAHDOD",
                self.mexico_namahdod_panel_url,
                self.mexico_namahdod_panel_username,
                self.mexico_namahdod_panel_password,
                self.mexico_namahdod_panel_group_ids,
            ),
        ]
        for prefix, url, username, password, group_ids in mexico_panels:
            any_value = bool(url or username or password)
            if not any_value:
                continue
            if not url:
                missing.append(f"{prefix}_PANEL_URL")
            if not username:
                missing.append(f"{prefix}_PANEL_USERNAME")
            if not password:
                missing.append(f"{prefix}_PANEL_PASSWORD")
            if not group_ids:
                missing.append(f"{prefix}_PANEL_GROUP_IDS")
        if missing:
            raise RuntimeError(f"Missing required settings: {', '.join(missing)}")
