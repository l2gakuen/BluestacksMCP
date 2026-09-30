import asyncio

import pytest

from src.server.mcp import build_mcp, current_client
from src.config import Settings
from src.core.automation import AutomationCore
from src.adapters.adb import Adb
from tests.test_ui import XML


def call(server, name, args=None):
    return asyncio.run(server.call_tool(name, args or {}))


def test_tools_registered_and_call(core, settings, runner):
    runner.ui_xml = XML
    srv = build_mcp(core, settings)
    names = {t.name for t in asyncio.run(srv.list_tools())}
    for n in ("android_list_apps", "android_launch_app", "android_stop_app", "android_dump_ui",
              "android_extract_text", "android_click_text", "android_click_element", "android_scroll",
              "android_pull_to_refresh", "android_tap", "android_long_press", "android_swipe",
              "android_type", "android_press", "android_screenshot"):
        assert n in names
    r = call(srv, "android_click_text", {"text": "Login"})
    assert "click_text" in str(r)
    r = call(srv, "android_click_text", {"text": "Nope"})
    assert "ELEMENT_NOT_FOUND" in str(r)
    assert "image" in str(call(srv, "android_screenshot")).lower()


def test_allowlist(core, settings):
    s2 = settings.model_copy(update={"enabled_tools": ["android_screenshot"]})
    names = {t.name for t in asyncio.run(build_mcp(core, s2).list_tools())}
    assert names == {"android_screenshot"}


def test_http_requires_bearer(core, settings):
    from starlette.testclient import TestClient
    from src.server.mcp import create_mcp_app
    with TestClient(create_mcp_app(core, settings)) as c:
        assert c.post("/mcp", json={}).status_code == 401
        assert c.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.post("/mcp", json={}, headers={"Authorization": "Bearer secret"}).status_code != 401
