from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

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
    hwid_limit: int | None = None

    def payload(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        protocols = sorted(self.inbounds)
        unlimited_time = self.duration_days <= 0 or self.mode == "unlimited"
        payload: dict[str, Any] = {
            "username": self.username,
            "status": (
                "active"
                if unlimited_time
                else ("on_hold" if self.mode == "on_hold" else "active")
            ),
            "data_limit": self.volume_gb * 1024**3 if self.volume_gb > 0 else 0,
            "data_limit_reset_strategy": "no_reset",
            "proxies": {protocol: {} for protocol in protocols},
            "inbounds": self.inbounds,
        }
        if unlimited_time:
            payload.update(
                {
                    "expire": 0,
                    "on_hold_expire_duration": None,
                }
            )
        elif self.mode == "on_hold":
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
        subscription_base_url: str | None = None,
        fallback_base_urls: tuple[str, ...] = (),
        request_timeout_seconds: float = 30,
        connect_timeout_seconds: float = 15,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.subscription_base_url = (subscription_base_url or base_url).rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None
        base_urls = list(
            dict.fromkeys(
                url.rstrip("/")
                for url in (self.base_url, *fallback_base_urls)
                if url and url.rstrip("/")
            )
        )
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        }
        self._clients = [
            httpx.AsyncClient(
                base_url=url,
                verify=verify_ssl,
                timeout=httpx.Timeout(
                    request_timeout_seconds,
                    connect=connect_timeout_seconds,
                ),
                transport=transport,
                headers=headers,
            )
            for url in base_urls
        ]
        self._client = self._clients[0]

    async def close(self) -> None:
        for client in self._clients:
            await client.aclose()

    async def authenticate(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        last_error: MarzbanError | None = None
        ordered_clients = [
            self._client,
            *(client for client in self._clients if client is not self._client),
        ]
        for client in ordered_clients:
            try:
                response = await client.post(
                    "/api/admin/token",
                    data={"username": self.username, "password": self.password},
                )
                self._raise(response)
                token = response.json().get("access_token")
                if not token:
                    raise MarzbanError("پنل توکن دسترسی برنگرداند.")
            except httpx.HTTPError as exc:
                last_error = MarzbanError(f"ارتباط با پنل برقرار نشد: {exc}")
                continue
            except (MarzbanError, ValueError) as exc:
                last_error = exc if isinstance(exc, MarzbanError) else MarzbanError(
                    "پاسخ ورود پنل معتبر نیست."
                )
                continue
            self._client = client
            self._token = str(token)
            return self._token
        raise last_error or MarzbanError("ارتباط با پنل برقرار نشد.")

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        token = await self.authenticate()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise MarzbanError(f"ارتباط با پنل برقرار نشد: {exc}") from exc
        if response.status_code == 401:
            token = await self.authenticate(force=True)
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = await self._client.request(method, path, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                raise MarzbanError(f"ارتباط با پنل برقرار نشد: {exc}") from exc
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

    def absolute_subscription_url(self, url: str) -> str:
        subscription_url = url.strip()
        parsed = urlparse(subscription_url)
        if parsed.scheme and parsed.netloc:
            subscription_url = urlunparse(
                ("", "", parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
        return urljoin(f"{self.subscription_base_url}/", subscription_url)


class EasyPanelClient(MarzbanClient):
    def __init__(
        self,
        *args,
        group_ids: tuple[int, ...] = (1,),
        hwid_limit: int | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.group_ids = list(group_ids)
        self.hwid_limit = hwid_limit

    def update_settings(
        self,
        *,
        group_ids: tuple[int, ...] | list[int] | None = None,
        hwid_limit: int | None | object = ...,
    ) -> None:
        if group_ids is not None:
            self.group_ids = [int(item) for item in group_ids]
        if hwid_limit is not ...:
            self.hwid_limit = None if hwid_limit is None else int(hwid_limit)

    async def create_user(self, spec: CreateSpec) -> dict[str, Any]:
        payload = spec.payload()
        payload.pop("proxies", None)
        payload.pop("inbounds", None)
        payload["group_ids"] = self.group_ids
        hwid_limit = spec.hwid_limit if spec.hwid_limit is not None else self.hwid_limit
        if hwid_limit is not None:
            payload["hwid_limit"] = int(hwid_limit)
        return (await self._request("POST", "/api/user", json=payload)).json()


class PasarguardClient(EasyPanelClient):
    async def get_inbounds(self) -> dict[str, list[dict[str, Any]]]:
        payload = (await self._request("GET", "/api/inbounds")).json()
        if isinstance(payload, list):
            return {
                "vless": [
                    {"tag": str(item).strip()}
                    for item in payload
                    if str(item).strip()
                ]
            }
        return payload if isinstance(payload, dict) else {}

    async def create_user(self, spec: CreateSpec) -> dict[str, Any]:
        payload = spec.payload()
        if self.group_ids:
            # Group selection replaces per-inbound selection for Pasarguard.
            payload.pop("proxies", None)
            payload.pop("inbounds", None)
            payload["group_ids"] = self.group_ids
        hwid_limit = spec.hwid_limit if spec.hwid_limit is not None else self.hwid_limit
        if hwid_limit is not None:
            payload["hwid_limit"] = int(hwid_limit)
        return (await self._request("POST", "/api/user", json=payload)).json()
