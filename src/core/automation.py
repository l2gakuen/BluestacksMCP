from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from src.adapters.adb import Adb
from src.adapters.uiautomator import UiAutomator
from src.config import Settings
from src.core.device_manager import DeviceManager
from src.core import selectors as sel_mod
from src.core.context import request_id
from src.core.errors import AutomationError
from src.models.actions import KEYS, Selector

log = logging.getLogger("automation")

KEYCODES = {"BACK": 4, "HOME": 3, "ENTER": 66, "TAB": 61, "ESC": 111, "DEL": 67, "MENU": 82,
            "APP_SWITCH": 187, "VOLUME_UP": 24, "VOLUME_DOWN": 25,
            "DPAD_UP": 19, "DPAD_DOWN": 20, "DPAD_LEFT": 21, "DPAD_RIGHT": 22}
assert set(KEYCODES) == set(KEYS)


def _input_escape(text: str) -> str:
    # `adb shell input text` goes through the device shell: %s = space, escape shell metachars.
    out = []
    for ch in text:
        if ch == " ":
            out.append("%s")
        elif ch.isalnum() or ch in "._-@:,/+=":
            out.append(ch)
        else:
            out.append("\\" + ch)
    return "".join(out)


class AutomationCore:
    """Single implementation of every operation; REST and MCP only call this."""

    def __init__(self, settings: Settings, adb: Adb | None = None):
        self.s = settings
        self.adb = adb or Adb(settings.adb_binary)
        self.dm = DeviceManager(settings, self.adb)
        self.ui = UiAutomator(self.adb)

    # ---- helpers
    def _timeout(self, timeout_ms: int | None) -> float:
        return (timeout_ms or self.s.action_timeout_ms) / 1000

    @contextmanager
    def _op(self, device_id: str | None, op: str, **fields):
        """Verify device, hold the per-device lock, log op (never text contents)."""
        did, serial = self.dm.ensure_online(device_id)
        t0 = time.monotonic()
        code = "OK"
        with self.dm.locks[did]:
            try:
                yield did, serial
            except AutomationError as e:
                code = e.code
                raise
            finally:
                log.info("request_id=%s operation=%s device_id=%s duration_ms=%d result=%s %s", request_id.get(), op, did,
                         (time.monotonic() - t0) * 1000, code,
                         " ".join(f"{k}={v}" for k, v in fields.items()))

    def _result(self, did: str, action: str, t0: float, **extra) -> dict:
        return {"success": True, "device_id": did, "action": action,
                "duration_ms": int((time.monotonic() - t0) * 1000), **extra}

    # ---- device
    def list_devices(self):
        return self.dm.list()

    def get_device(self, device_id: str | None):
        return self.dm.status(device_id)

    device_status = get_device

    def connect(self, device_id: str | None):
        return self.dm.connect(device_id)

    def disconnect(self, device_id: str | None):
        return self.dm.disconnect(device_id)

    # ---- input
    def tap(self, device_id, x: int, y: int, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "tap") as (did, ser):
            self.adb.shell(ser, ["input", "tap", str(x), str(y)], self._timeout(timeout_ms))
        return self._result(did, "tap", t0, target=f"{x},{y}")

    def long_press(self, device_id, x: int, y: int, duration_ms: int = 1000, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "long_press") as (did, ser):
            self.adb.shell(ser, ["input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
                           self._timeout(timeout_ms) + duration_ms / 1000)
        return self._result(did, "long_press", t0, target=f"{x},{y}")

    def swipe(self, device_id, x1, y1, x2, y2, duration_ms: int = 300, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "swipe") as (did, ser):
            self.adb.shell(ser, ["input", "swipe", *map(str, (x1, y1, x2, y2, duration_ms))],
                           self._timeout(timeout_ms) + duration_ms / 1000)
        return self._result(did, "swipe", t0)

    def type_text(self, device_id, text: str, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "type_text", text_length=len(text)) as (did, ser):
            self.adb.shell(ser, ["input", "text", _input_escape(text)], self._timeout(timeout_ms))
        return self._result(did, "type_text", t0, text_length=len(text))

    def press(self, device_id, key: str, timeout_ms=None):
        if key not in KEYCODES:
            raise AutomationError("INVALID_ACTION", f"Unsupported key '{key}'.", {"supported": list(KEYCODES)})
        t0 = time.monotonic()
        with self._op(device_id, "press", key=key) as (did, ser):
            self.adb.shell(ser, ["input", "keyevent", str(KEYCODES[key])], self._timeout(timeout_ms))
        return self._result(did, "press", t0, target=key)

    # ---- apps
    def launch_app(self, device_id, package: str, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "launch_app", package=package) as (did, ser):
            self._require_package(ser, package)
            self.adb.shell(ser, ["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"],
                           self._timeout(timeout_ms))
        return self._result(did, "launch_app", t0, target=package)

    def stop_app(self, device_id, package: str, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "stop_app", package=package) as (did, ser):
            self._require_package(ser, package)
            self.adb.shell(ser, ["am", "force-stop", package], self._timeout(timeout_ms))
        return self._result(did, "stop_app", t0, target=package)

    def current_app(self, device_id, timeout_ms=None):
        with self._op(device_id, "current_app") as (did, ser):
            out = self.adb.shell(ser, ["dumpsys", "window"], self._timeout(timeout_ms))
        pkg = activity = None
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                for tok in line.replace("}", " ").split():
                    if "/" in tok and "." in tok:
                        pkg, activity = tok.split("/", 1)
                        break
                if pkg:
                    break
        return {"device_id": did, "package": pkg, "activity": activity}

    def _require_package(self, serial: str, package: str):
        out = self.adb.shell(serial, ["pm", "path", package], self._timeout(None))
        if "package:" not in out:
            raise AutomationError("APP_NOT_FOUND", f"Package '{package}' is not installed.",
                                  {"package": package})

    # ---- visual
    def screenshot(self, device_id, timeout_ms=None) -> bytes:
        with self._op(device_id, "screenshot") as (did, ser):
            png = self.adb.screencap(ser, self._timeout(timeout_ms))
        if not png.startswith(b"\x89PNG"):
            raise AutomationError("ADB_ERROR", "Device did not return a PNG.")
        if len(png) > self.s.screenshot_max_size_mb * 1024 * 1024:
            raise AutomationError("INVALID_ACTION", "Screenshot exceeds size limit.",
                                  {"max_mb": self.s.screenshot_max_size_mb})
        return png

    @staticmethod
    def png_size(png: bytes) -> tuple[int, int]:
        return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")

    # ---- semantic UI
    def _dump(self, serial: str, timeout_ms=None) -> list[dict]:
        return self.ui.dump(serial, self._timeout(timeout_ms))

    def dump_ui(self, device_id, timeout_ms=None) -> dict:
        with self._op(device_id, "dump_ui") as (did, ser):
            els = self._dump(ser, timeout_ms)
        return {"device_id": did, "elements": els}

    def _locate(self, ser: str, selector: Selector, wait_ms: int | None) -> dict:
        """Poll until the selector matches or the wait budget elapses (0 polls once if wait_ms falsy)."""
        deadline = time.monotonic() + (wait_ms or 0) / 1000
        while True:
            el = sel_mod.find_one(self._dump(ser), selector)
            if el:
                return el
            if time.monotonic() >= deadline:
                raise AutomationError("ELEMENT_NOT_FOUND", "No visible element matched the selector.",
                                      {"selector": selector.model_dump(exclude_none=True)})
            time.sleep(0.4)

    def find_element(self, device_id, selector, timeout_ms=None) -> dict:
        s = sel_mod.to_selector(selector)
        with self._op(device_id, "find_element") as (did, ser):
            el = self._locate(ser, s, None)
        return {"device_id": did, "element": el}

    def find_text(self, device_id, text: str, timeout_ms=None) -> dict:
        return self.find_element(device_id, Selector(text=text), timeout_ms)

    def click_element(self, device_id, selector, timeout_ms=None) -> dict:
        s = sel_mod.to_selector(selector)
        t0 = time.monotonic()
        with self._op(device_id, "click_element") as (did, ser):
            el = self._locate(ser, s, timeout_ms)
            if not el["enabled"]:
                raise AutomationError("ELEMENT_NOT_CLICKABLE", "Matched element is disabled.",
                                      {"selector": s.model_dump(exclude_none=True)})
            x, y = sel_mod.center(el)
            self.adb.shell(ser, ["input", "tap", str(x), str(y)], self._timeout(None))
        return self._result(did, "click_element", t0, target=s.model_dump(exclude_none=True))

    def click_text(self, device_id, text: str, timeout_ms=None) -> dict:
        r = self.click_element(device_id, Selector(text=text), timeout_ms)
        r["action"], r["target"] = "click_text", text
        return r

    def set_text(self, device_id, selector, text: str, timeout_ms=None) -> dict:
        s = sel_mod.to_selector(selector)
        t0 = time.monotonic()
        with self._op(device_id, "set_text", text_length=len(text)) as (did, ser):
            el = self._locate(ser, s, timeout_ms)
            x, y = sel_mod.center(el)
            to = self._timeout(None)
            self.adb.shell(ser, ["input", "tap", str(x), str(y)], to)
            # clear existing content: jump to end, delete one key per char
            self.adb.shell(ser, ["input", "keyevent", "123"] + ["67"] * len(el["text"]), to)
            if text:
                self.adb.shell(ser, ["input", "text", _input_escape(text)], to)
        return self._result(did, "set_text", t0, text_length=len(text))

    def wait_for_element(self, device_id, selector, timeout_ms=None) -> dict:
        s = sel_mod.to_selector(selector)
        t0 = time.monotonic()
        with self._op(device_id, "wait_for_element") as (did, ser):
            try:
                el = self._locate(ser, s, timeout_ms or self.s.ui_wait_timeout_ms)
            except AutomationError as e:
                if e.code == "ELEMENT_NOT_FOUND":
                    raise AutomationError("TIMEOUT", "Timed out waiting for element.", e.details)
                raise
        return self._result(did, "wait_for_element", t0, element=el)

    def wait_for_text(self, device_id, text: str, timeout_ms=None) -> dict:
        r = self.wait_for_element(device_id, Selector(text=text), timeout_ms)
        r["action"], r["target"] = "wait_for_text", text
        return r

    # ---- app listing
    def list_apps(self, device_id, include_system: bool = False, timeout_ms=None) -> dict:
        with self._op(device_id, "list_apps") as (did, ser):
            args = ["pm", "list", "packages"] + ([] if include_system else ["-3"])
            out = self.adb.shell(ser, args, self._timeout(timeout_ms))
        pkgs = sorted(l[8:].strip() for l in out.splitlines() if l.startswith("package:"))
        return {"device_id": did, "packages": pkgs}

    # ---- data parsing
    def extract_text(self, device_id, pattern: str | None = None, timeout_ms=None) -> dict:
        """Visible on-screen text/content-desc in reading order (top->bottom, left->right); optional regex filter."""
        import re
        try:
            rx = re.compile(pattern) if pattern else None
        except re.error as e:
            raise AutomationError("INVALID_ACTION", f"Bad regex: {e}")
        with self._op(device_id, "extract_text") as (did, ser):
            els = self._dump(ser, timeout_ms)
        items = sorted((e for e in els if e["visible"] and (e["text"] or e["content_desc"])),
                       key=lambda e: (e["bounds"][1], e["bounds"][0]))
        out = [{"text": e["text"] or e["content_desc"], "resource_id": e["resource_id"],
                "bounds": e["bounds"]} for e in items]
        if rx:
            out = [o for o in out if rx.search(o["text"])]
        return {"device_id": did, "items": out}

    # ---- gestures
    def _screen_size(self, ser: str) -> tuple[int, int]:
        out = self.adb.shell(ser, ["wm", "size"], self._timeout(None))
        for tok in reversed(out.split()):
            if "x" in tok:
                try:
                    w, h = tok.split("x")
                    return int(w), int(h)
                except ValueError:
                    pass
        raise AutomationError("ADB_ERROR", "Could not read screen size.")

    def scroll(self, device_id, direction: str, distance_pct: int = 50, duration_ms: int = 400, timeout_ms=None):
        """direction = which way the content moves' *view* goes (down = see content further down)."""
        if direction not in ("up", "down", "left", "right"):
            raise AutomationError("INVALID_ACTION", "direction must be up/down/left/right.")
        t0 = time.monotonic()
        with self._op(device_id, "scroll", direction=direction) as (did, ser):
            w, h = self._screen_size(ser)
            cx, cy, d = w // 2, h // 2, distance_pct / 100
            dx, dy = int(w * d / 2), int(h * d / 2)
            # finger moves opposite to the direction the view scrolls
            x1, y1, x2, y2 = {"down": (cx, cy + dy, cx, cy - dy), "up": (cx, cy - dy, cx, cy + dy),
                              "right": (cx + dx, cy, cx - dx, cy), "left": (cx - dx, cy, cx + dx, cy)}[direction]
            self.adb.shell(ser, ["input", "swipe", *map(str, (x1, y1, x2, y2, duration_ms))],
                           self._timeout(timeout_ms) + duration_ms / 1000)
        return self._result(did, "scroll", t0, target=direction)

    def pull_to_refresh(self, device_id, timeout_ms=None):
        t0 = time.monotonic()
        with self._op(device_id, "pull_to_refresh") as (did, ser):
            w, h = self._screen_size(ser)
            self.adb.shell(ser, ["input", "swipe", str(w // 2), str(h // 5), str(w // 2), str(h * 3 // 5), "500"],
                           self._timeout(timeout_ms) + 0.5)
        return self._result(did, "pull_to_refresh", t0)

    # ---- workflows
    MAX_WORKFLOW_STEPS = 50

    def run_workflow(self, device_id, steps: list) -> dict:
        """Run steps sequentially through this core; stop at the first failure."""
        if len(steps) > self.MAX_WORKFLOW_STEPS:
            raise AutomationError("INVALID_ACTION", f"Max {self.MAX_WORKFLOW_STEPS} steps.")
        t0 = time.monotonic()
        results = []
        for i, st in enumerate(steps):
            d = st.model_dump(exclude_none=True)
            kind = d.pop("type")
            fn = {"tap": lambda: self.tap(device_id, d["x"], d["y"]),
                  "long_press": lambda: self.long_press(device_id, d["x"], d["y"], d.get("duration_ms", 1000)),
                  "swipe": lambda: self.swipe(device_id, d["x1"], d["y1"], d["x2"], d["y2"], d.get("duration_ms", 300)),
                  "type": lambda: self.type_text(device_id, d["text"]),
                  "press": lambda: self.press(device_id, d["key"]),
                  "click_text": lambda: self.click_text(device_id, d["text"], d.get("timeout_ms")),
                  "click_element": lambda: self.click_element(device_id, d["selector"], d.get("timeout_ms")),
                  "set_text": lambda: self.set_text(device_id, d["selector"], d["text"], d.get("timeout_ms")),
                  "wait_text": lambda: self.wait_for_text(device_id, d["text"], d.get("timeout_ms")),
                  "wait_element": lambda: self.wait_for_element(device_id, d["selector"], d.get("timeout_ms")),
                  "launch_app": lambda: self.launch_app(device_id, d["package"]),
                  "stop_app": lambda: self.stop_app(device_id, d["package"]),
                  "scroll": lambda: self.scroll(device_id, d["direction"], d.get("distance_pct", 50)),
                  "pull_to_refresh": lambda: self.pull_to_refresh(device_id)}[kind]
            try:
                r = fn()
                results.append({"step": i, "type": kind, "success": True, "duration_ms": r.get("duration_ms")})
            except AutomationError as e:
                results.append({"step": i, "type": kind, "success": False, "error": e.to_dict()})
                return {"success": False, "device_id": device_id, "failed_step": i, "results": results,
                        "duration_ms": int((time.monotonic() - t0) * 1000)}
        return {"success": True, "device_id": device_id, "results": results,
                "duration_ms": int((time.monotonic() - t0) * 1000)}
