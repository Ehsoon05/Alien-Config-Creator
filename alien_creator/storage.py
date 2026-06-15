from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS = {
    "selected_inbounds": {},
    "default_mode": "on_hold",
    "default_volume_gb": 30,
    "default_duration_days": 30,
}


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            for key, value in DEFAULT_SETTINGS.items():
                connection.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
            connection.commit()

    async def get(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            return await asyncio.to_thread(self._get_sync, key, default)

    def _get_sync(self, key: str, default: Any) -> Any:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        return json.loads(row[0]) if row else default

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            await asyncio.to_thread(self._set_sync, key, value)

    def _set_sync(self, key: str, value: Any) -> None:
        serialized = json.dumps(value, ensure_ascii=False)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, serialized),
            )
            connection.commit()

