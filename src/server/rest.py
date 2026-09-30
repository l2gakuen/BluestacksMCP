from __future__ import annotations

import re
import uuid

from src.core.context import request_id

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from src.config import Settings
from src.core.automation import AutomationCore
from src.core.errors import AutomationError
from src.models import actions as A
from src.security.auth import authenticate, authorize

VERSION = "1.0.0"
MAX_BODY = 64 * 1024
_RID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def create_app(core: AutomationCore, settings: Settings) -> FastAPI:
    docs = not settings.production
    app = FastAPI(title="BlueStacks Automation Node", version=VERSION,
                  docs_url="/api/docs" if docs else None,
                  openapi_url="/api/openapi.json" if docs else None, redoc_url=None)

    def err(e: AutomationError, rid: str | None = None):
        return JSONResponse({"error": e.to_dict()}, status_code=e.status,
                            headers={"X-Request-ID": rid} if rid else None)

    @app.middleware("http")
    async def request_id_and_limits(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        rid = rid if _RID.match(rid) else uuid.uuid4().hex
        request.state.request_id = rid
        request_id.set(rid)
        if int(request.headers.get("content-length") or 0) > MAX_BODY:
            return JSONResponse({"error": {"code": "INVALID_ACTION", "message": "Request too large.",
                                           "details": {}}}, status_code=413, headers={"X-Request-ID": rid})
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        return resp

    @app.exception_handler(AutomationError)
    async def _ae(request: Request, e: AutomationError):
        return err(e, getattr(request.state, "request_id", None))

    @app.exception_handler(RequestValidationError)
    async def _ve(request: Request, e: RequestValidationError):
        errs = [{"loc": list(x["loc"]), "msg": x["msg"]} for x in e.errors()]
        return err(AutomationError("INVALID_ACTION", "Invalid request.", {"errors": errs}),
                   getattr(request.state, "request_id", None))

    @app.exception_handler(Exception)
    async def _ie(request: Request, e: Exception):
        return err(AutomationError("INTERNAL_ERROR", "Internal error."), getattr(request.state, "request_id", None))

    def auth(request: Request) -> str:
        client = authenticate(settings, request.headers.get("authorization"))
        request.state.client = client
        return client

    def guard(client: str, device_id: str | None, tool: str) -> None:
        authorize(settings, client, device_id, tool)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": VERSION}

    @app.get("/api/v1/health/devices")
    def health_devices(client: str = Depends(auth)):
        guard(client, None, "health_devices")
        devs = {d.id: {"connected": d.connected} for d in core.list_devices()
                if not settings.clients.get(client) or not settings.clients[client].devices
                or d.id in settings.clients[client].devices}
        return {"status": "ok", "devices": devs}

    @app.get("/api/v1/devices")
    def devices(client: str = Depends(auth)):
        guard(client, None, "android_list_devices")
        c = settings.clients.get(client)
        return [d for d in core.list_devices() if not c or not c.devices or d.id in c.devices]

    @app.get("/api/v1/devices/{device_id}")
    def device(device_id: str, client: str = Depends(auth)):
        guard(client, device_id, "android_device_status")
        return core.get_device(device_id)

    @app.get("/api/v1/devices/{device_id}/screenshot")
    def screenshot(device_id: str, client: str = Depends(auth)):
        guard(client, device_id, "android_screenshot")
        return Response(core.screenshot(device_id), media_type="image/png")

    @app.get("/api/v1/devices/{device_id}/ui")
    def ui(device_id: str, timeout_ms: int | None = Query(default=None, ge=100, le=60000),
           client: str = Depends(auth)):
        guard(client, device_id, "android_dump_ui")
        return core.dump_ui(device_id, timeout_ms)

    @app.get("/api/v1/devices/{device_id}/apps")
    def apps(device_id: str, include_system: bool = False, client: str = Depends(auth)):
        guard(client, device_id, "android_list_apps")
        return core.list_apps(device_id, include_system)

    @app.get("/api/v1/devices/{device_id}/app")
    def current_app(device_id: str, client: str = Depends(auth)):
        guard(client, device_id, "android_current_app")
        return core.current_app(device_id)

    def post(path: str, tool: str, model, fn):
        def handler(device_id: str, body, client: str = Depends(auth)):
            guard(client, device_id, tool)
            return fn(device_id, body)
        handler.__annotations__["body"] = model  # `from __future__ annotations` can't resolve closures
        app.post(f"/api/v1/devices/{{device_id}}/{path}")(handler)

    post("actions/tap", "android_tap", A.Tap, lambda d, b: core.tap(d, b.x, b.y))
    post("actions/long_press", "android_long_press", A.LongPress,
         lambda d, b: core.long_press(d, b.x, b.y, b.duration_ms))
    post("actions/swipe", "android_swipe", A.Swipe,
         lambda d, b: core.swipe(d, b.x1, b.y1, b.x2, b.y2, b.duration_ms))
    post("actions/type", "android_type", A.TypeText, lambda d, b: core.type_text(d, b.text))
    post("actions/press", "android_press", A.Press, lambda d, b: core.press(d, b.key))
    post("actions/click", "android_click_element", A.ClickReq,
         lambda d, b: core.click_text(d, b.text, b.timeout_ms) if b.text is not None
         else core.click_element(d, b.selector, b.timeout_ms))
    post("actions/set_text", "android_set_text", A.SetTextReq,
         lambda d, b: core.set_text(d, b.selector, b.text, b.timeout_ms))
    post("actions/launch_app", "android_launch_app", A.AppReq, lambda d, b: core.launch_app(d, b.package))
    post("actions/stop_app", "android_stop_app", A.AppReq, lambda d, b: core.stop_app(d, b.package))
    post("wait/text", "android_wait_for_text", A.WaitText,
         lambda d, b: core.wait_for_text(d, b.text, b.timeout_ms))
    post("wait/element", "android_wait_for_element", A.WaitElement,
         lambda d, b: core.wait_for_element(d, b.selector, b.timeout_ms))
    post("actions/scroll", "android_scroll", A.Scroll, lambda d, b: core.scroll(d, b.direction, b.distance_pct))
    post("actions/pull_to_refresh", "android_pull_to_refresh", A.Empty, lambda d, b: core.pull_to_refresh(d))
    post("extract", "android_extract_text", A.ExtractReq, lambda d, b: core.extract_text(d, b.pattern))
    post("workflows", "android_workflow", A.WorkflowReq, lambda d, b: core.run_workflow(core.dm.resolve(d), b.actions))
    post("find", "android_find_text", A.ClickReq,
         lambda d, b: core.find_text(d, b.text) if b.text is not None else core.find_element(d, b.selector))

    return app
