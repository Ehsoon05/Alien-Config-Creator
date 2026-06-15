from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


class MarzbanError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreateSpec:
    username: str
    volume_gb: int
    duration_days: int
    mode: str
    inbounds: dict[str, list[str]]

    def payload(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        protocols = sorted(self.inbounds)
        payload: dict[str, Any] = {
            "username": self.username,
            "status": "on_hold" if self.mode == "on_hold" else "active",
            "data_limit": self.volume_gb * 1024**3 if self.volume_gb > 0 else 0,
            "data_limit_reset_strategy": "no_reset",
            "proxies": {protocol: {} for protocol in protocols},
            "inbounds": self.inbounds,
        }
        if self.mode == "on_hold":
            payload.update(
                {
                    "expire": 0,
                    "on_hold_expire_duration": self.duration_days * 86400,
                }
            )
        else:
            payload.update(
                {
                    "expire": int((now + timedelta(days=self.duration_days)).timestamp()),
                    "on_hold_expire_duration": None,
                }
            )
        return payload


class MarzbanClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=verify_ssl,
            timeout=httpx.Timeout(30, connect=15),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def authenticate(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        response = await self._client.post(
            "/api/admin/token",
            data={"username": self.username, "password": self.password},
        )
        self._raise(response)
        self._token = response.json()["access_token"]
        return self._token

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        token = await self.authenticate()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        response = await self._client.request(method, path, headers=headers, **kwargs)
        if response.status_code == 401:
            token = await self.authenticate(force=True)
            headers["Authorization"] = f"Bearer {token}"
            response = await self._client.request(method, path, headers=headers, **kwargs)
        self._raise(response)
        return response

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise MarzbanError(f"Marzban API {response.status_code}: {detail}")

    async def get_inbounds(self) -> dict[str, list[dict[str, Any]]]:
        return (await self._request("GET", "/api/inbounds")).json()

    async def create_user(self, spec: CreateSpec) -> dict[str, Any]:
        return (await self._request("POST", "/api/user", json=spec.payload())).json()


class EasyPanelClient(MarzbanClient):
    def __init__(self, *args, group_ids: tuple[int, ...] = (1,), **kwargs):
        super().__init__(*args, **kwargs)
        self.group_ids = list(group_ids)

    async def create_user(self, spec: CreateSpec) -> dict[str, Any]:
        payload = spec.payload()
        payload.pop("proxies", None)
        payload.pop("inbounds", None)
        payload["group_ids"] = self.group_ids
        return (await self._request("POST", "/api/user", json=payload)).json()
