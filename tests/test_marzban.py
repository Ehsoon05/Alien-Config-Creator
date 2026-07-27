import re
from datetime import datetime, timezone

import httpx
import pytest

from alien_creator.bot import PANEL_BUTTON_PATTERN, PANEL_BUTTONS, _phantom_subscription_payload
from alien_creator.marzban import CreateSpec, EasyPanelClient, MarzbanClient, MarzbanError


INBOUNDS = {"vless": ["VLESS WS", "VLESS REALITY"]}


def test_on_hold_payload():
    payload = CreateSpec(
        username="Alien_1",
        volume_gb=30,
        duration_days=30,
        mode="on_hold",
        inbounds=INBOUNDS,
    ).payload(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert payload["status"] == "on_hold"
    assert payload["expire"] == 0
    assert payload["on_hold_expire_duration"] == 30 * 86400
    assert payload["data_limit"] == 30 * 1024**3
    assert payload["proxies"] == {"vless": {}}
    assert "note" not in payload


def test_phantom_subscription_payload_includes_device_limit():
    payload = _phantom_subscription_payload(
        token="abc",
        upstream_url="https://panel.example/sub/abc",
        username="Alien_1",
        volume_gb=30,
        subscription_options={"device_limit": 2},
        panel_key="easy",
    )
    assert payload["device_limit"] == 2
    assert payload["service_name"] == "Alien_1"


def test_phantom_subscription_payload_includes_advanced_options():
    payload = _phantom_subscription_payload(
        token="abc",
        upstream_url="https://panel.example/sub/abc",
        username="Alien_1",
        volume_gb=30,
        subscription_options={
            "profile_title": "Phantom VIP",
            "device_limit": 3,
            "channel_handle": "@PhantomHubs",
            "show_header": False,
            "show_config_preview": False,
            "info_proxies_enabled": True,
        },
        panel_key="svn",
    )
    assert payload["profile_title"] == "Phantom VIP"
    assert payload["channel_handle"] == "@PhantomHubs"
    assert payload["device_limit"] == 3
    assert payload["show_header"] is False
    assert payload["show_config_preview"] is False
    assert payload["info_proxies_enabled"] is True


def test_dated_payload():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    payload = CreateSpec(
        username="Alien_1",
        volume_gb=0,
        duration_days=10,
        mode="date",
        inbounds=INBOUNDS,
    ).payload(now)
    assert payload["status"] == "active"
    assert payload["data_limit"] == 0
    assert payload["expire"] == int(datetime(2026, 1, 11, tzinfo=timezone.utc).timestamp())


def test_unlimited_time_payload():
    payload = CreateSpec(
        username="Alien_1",
        volume_gb=0,
        duration_days=10,
        mode="unlimited",
        inbounds=INBOUNDS,
    ).payload(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert payload["status"] == "active"
    assert payload["expire"] == 0
    assert payload["on_hold_expire_duration"] is None


def test_zero_duration_payload_is_unlimited_time():
    payload = CreateSpec(
        username="Alien_1",
        volume_gb=30,
        duration_days=0,
        mode="on_hold",
        inbounds=INBOUNDS,
    ).payload(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert payload["status"] == "active"
    assert payload["expire"] == 0
    assert payload["on_hold_expire_duration"] is None


@pytest.mark.asyncio
async def test_client_authenticates_and_creates_user():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token", "token_type": "bearer"})
        return httpx.Response(
            200,
            json={"username": "Alien_1", "subscription_url": "https://example.com/sub/1"},
        )

    client = MarzbanClient(
        "https://example.com",
        "admin",
        "password",
        transport=httpx.MockTransport(handler),
    )
    try:
        response = await client.create_user(
            CreateSpec("Alien_1", 10, 30, "on_hold", INBOUNDS)
        )
    finally:
        await client.close()

    assert response["subscription_url"].endswith("/1")
    assert requests[1].headers["authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_client_can_use_separate_api_and_subscription_urls():
    client = MarzbanClient(
        "https://127.0.0.1:18443",
        "admin",
        "password",
        subscription_base_url="https://youpanel.example.com:2053",
        verify_ssl=False,
    )
    try:
        assert (
            client.absolute_subscription_url("/sub/example")
            == "https://youpanel.example.com:2053/sub/example"
        )
        assert (
            client.absolute_subscription_url(
                "http://127.0.0.1:18443/sub/example?client=sing-box"
            )
            == "https://youpanel.example.com:2053/sub/example?client=sing-box"
        )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_client_wraps_network_errors():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("offline", request=request)

    client = MarzbanClient(
        "https://panel.example.com",
        "admin",
        "password",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(MarzbanError, match="ارتباط با پنل برقرار نشد"):
            await client.authenticate()
    finally:
        await client.close()


def test_panel_buttons_can_restart_an_expired_conversation():
    assert all(re.fullmatch(PANEL_BUTTON_PATTERN, label) for label in PANEL_BUTTONS)


@pytest.mark.asyncio
async def test_easy_panel_uses_multilocation_without_inbound_settings():
    payloads = []

    def handler(request: httpx.Request):
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        payloads.append(__import__("json").loads(request.content))
        return httpx.Response(201, json={"subscription_url": "https://p.example/sub/1"})

    client = EasyPanelClient(
        "https://p.example",
        "admin",
        "password",
        group_ids=(1,),
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.create_user(CreateSpec("Alien_2", 30, 30, "on_hold", INBOUNDS))
    finally:
        await client.close()

    assert payloads[0]["group_ids"] == [1]
    assert "proxies" not in payloads[0]
    assert "inbounds" not in payloads[0]


@pytest.mark.asyncio
async def test_easy_panel_can_send_hwid_limit():
    payloads = []

    def handler(request: httpx.Request):
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        payloads.append(__import__("json").loads(request.content))
        return httpx.Response(201, json={"subscription_url": "https://p.example/sub/1"})

    client = EasyPanelClient(
        "https://p.example",
        "admin",
        "password",
        group_ids=(1,),
        hwid_limit=2,
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.create_user(CreateSpec("Alien_3", 30, 30, "on_hold", INBOUNDS))
    finally:
        await client.close()

    assert payloads[0]["hwid_limit"] == 2


@pytest.mark.asyncio
async def test_easy_panel_create_spec_hwid_overrides_default():
    payloads = []

    def handler(request: httpx.Request):
        if request.url.path == "/api/admin/token":
            return httpx.Response(200, json={"access_token": "token"})
        payloads.append(__import__("json").loads(request.content))
        return httpx.Response(201, json={"subscription_url": "https://p.example/sub/1"})

    client = EasyPanelClient(
        "https://p.example",
        "admin",
        "password",
        group_ids=(1,),
        hwid_limit=2,
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.create_user(CreateSpec("Alien_4", 30, 30, "on_hold", INBOUNDS, hwid_limit=3))
    finally:
        await client.close()

    assert payloads[0]["hwid_limit"] == 3
