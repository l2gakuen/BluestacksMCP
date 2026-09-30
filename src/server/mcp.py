
import asyncio
import contextvars
import json
from typing import Annotated, Any, Callable

from pydantic import Field
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image

from src.config import Settings
from src.core.automation import AutomationCore
from src.core.errors import AutomationError
from src.models.actions import KEYS, PKG, Selector
from src.security.auth import authenticate, authorize

current_client: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_client", default="default")

Dev = Annotated[str | None, Field(description="Device id; optional when only one device is configured.")]
Timeout = Annotated[int | None, Field(ge=100, le=60000, description="Timeout in ms.")]
Pkg = Annotated[str, Field(pattern=PKG, max_length=255)]
Coord = Annotated[int, Field(ge=0, le=20000)]
Dur = Annotated[int, Field(ge=50, le=10000)]
ACT = "ACTS ON THE REMOTE ANDROID DEVICE. "


def build_mcp(core: AutomationCore, settings: Settings) -> MCPServer:
    server = MCPServer("bluestacks-android")

    def tool(name: str, desc: str):
        enabled = not settings.enabled_tools or name in settings.enabled_tools

        def deco(fn: Callable[..., Any]):
            if not enabled:
                return fn

            async def wrapper(**kw):
                try:
                    authorize(settings, current_client.get(), kw.get("device_id"), name)
                    res = await asyncio.to_thread(fn, **kw)
                    return res.model_dump() if hasattr(res, "model_dump") else res
                except AutomationError as e:
                    return {"success": False, "error": e.to_dict()}

            wrapper.__name__ = name
            wrapper.__annotations__ = {k: v for k, v in fn.__annotations__.items() if k != "return"}
            wrapper.__signature__ = __import__("inspect").signature(fn)  # keep defaults/types for the schema
            server.tool(name=name, description=desc)(wrapper)
            return fn
        return deco

    # ---- read-only
    @tool("android_list_devices", "List configured Android (BlueStacks) devices and their connection status.")
    def _(): 
        return {"devices": [d.model_dump() for d in core.list_devices()]}

    @tool("android_device_status", "Connection status and Android version of one device.")
    def _(device_id: Dev = None):
        return core.get_device(device_id)

    @tool("android_list_apps", "List installed apps (package names). Third-party only unless include_system=true.")
    def _(device_id: Dev = None, include_system: bool = False):
        return core.list_apps(device_id, include_system)

    @tool("android_current_app", "Get the foreground app package and activity.")
    def _(device_id: Dev = None):
        return core.current_app(device_id)

    @tool("android_dump_ui", "List all UI elements of the current screen as normalized JSON "
          "(text, content_desc, resource_id, class_name, clickable, enabled, visible, bounds).")
    def _(device_id: Dev = None, timeout_ms: Timeout = None):
        return core.dump_ui(device_id, timeout_ms)

    @tool("android_extract_text", "Parse on-screen data: visible text in reading order, optionally filtered by a regex.")
    def _(device_id: Dev = None, pattern: str | None = None):
        return core.extract_text(device_id, pattern)

    @tool("android_find_text", "Find a visible element by exact text (no action taken).")
    def _(text: str, device_id: Dev = None):
        return core.find_text(device_id, text)

    @tool("android_find_element", "Find a visible element by selector (no action taken).")
    def _(selector: Selector, device_id: Dev = None):
        return core.find_element(device_id, selector)

    @tool("android_screenshot", "Take a PNG screenshot of the device screen.")
    def _(device_id: Dev = None):
        png = core.screenshot(device_id)
        w, h = core.png_size(png)
        meta = {"device_id": core.dm.resolve(device_id), "width": w, "height": h, "format": "png"}
        return [Image(data=png, format="png"), json.dumps(meta)]

    @tool("android_wait_for_text", "Wait until visible text appears; TIMEOUT error otherwise.")
    def _(text: str, device_id: Dev = None, timeout_ms: Timeout = None):
        return core.wait_for_text(device_id, text, timeout_ms)

    @tool("android_wait_for_element", "Wait until an element matching the selector is visible.")
    def _(selector: Selector, device_id: Dev = None, timeout_ms: Timeout = None):
        return core.wait_for_element(device_id, selector, timeout_ms)

    # ---- apps
    @tool("android_launch_app", ACT + "Open (launch) an installed app by package name.")
    def _(package: Pkg, device_id: Dev = None):
        return core.launch_app(device_id, package)

    @tool("android_stop_app", ACT + "Close (force-stop) an app by package name.")
    def _(package: Pkg, device_id: Dev = None):
        return core.stop_app(device_id, package)

    # ---- touch
    @tool("android_tap", ACT + "Tap at screen coordinates. Prefer android_click_text/element when possible.")
    def _(x: Coord, y: Coord, device_id: Dev = None):
        return core.tap(device_id, x, y)

    @tool("android_long_press", ACT + "Long-press at screen coordinates.")
    def _(x: Coord, y: Coord, duration_ms: Dur = 1000, device_id: Dev = None):
        return core.long_press(device_id, x, y, duration_ms)

    @tool("android_swipe", ACT + "Swipe/drag between two coordinates.")
    def _(x1: Coord, y1: Coord, x2: Coord, y2: Coord, duration_ms: Dur = 300, device_id: Dev = None):
        return core.swipe(device_id, x1, y1, x2, y2, duration_ms)

    @tool("android_scroll", ACT + "Scroll the screen: direction is where the view moves (down = see content below).")
    def _(direction: str, distance_pct: Annotated[int, Field(ge=10, le=90)] = 50, device_id: Dev = None):
        return core.scroll(device_id, direction, distance_pct)

    @tool("android_pull_to_refresh", ACT + "Pull down from the top of the screen (pull-to-refresh gesture).")
    def _(device_id: Dev = None):
        return core.pull_to_refresh(device_id)

    @tool("android_click_text", ACT + "Click the visible element with exact text.")
    def _(text: str, device_id: Dev = None, timeout_ms: Timeout = None):
        return core.click_text(device_id, text, timeout_ms)

    @tool("android_click_element", ACT + "Click the element matching a selector (resource_id, content_desc, text, class_name, index).")
    def _(selector: Selector, device_id: Dev = None, timeout_ms: Timeout = None):
        return core.click_element(device_id, selector, timeout_ms)

    # ---- keyboard
    @tool("android_type", ACT + "Type text into the focused field.")
    def _(text: Annotated[str, Field(min_length=1, max_length=2000)], device_id: Dev = None):
        return core.type_text(device_id, text)

    @tool("android_set_text", ACT + "Replace the text of the element matching a selector.")
    def _(selector: Selector, text: Annotated[str, Field(max_length=2000)], device_id: Dev = None,
          timeout_ms: Timeout = None):
        return core.set_text(device_id, selector, text, timeout_ms)

    @tool("android_press", ACT + f"Press a key: {', '.join(KEYS)}.")
    def _(key: str, device_id: Dev = None):
        return core.press(device_id, key)

    return server


class BearerAuthASGI:
    """Reject non-authenticated HTTP requests to the MCP app; record client identity."""

    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            hdr = dict(scope["headers"]).get(b"authorization", b"").decode() or None
            try:
                tok = current_client.set(authenticate(self.settings, hdr))
            except AutomationError as e:
                body = json.dumps({"error": e.to_dict()}).encode()
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
            try:
                await self.app(scope, receive, send)
            finally:
                current_client.reset(tok)
        else:
            await self.app(scope, receive, send)


def create_mcp_app(core: AutomationCore, settings: Settings):
    server = build_mcp(core, settings)
    return BearerAuthASGI(server.streamable_http_app(host=settings.bind_host), settings)
