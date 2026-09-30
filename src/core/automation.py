from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from src.adapters.adb import Adb
from src.config import Settings
from src.core.device_manager import DeviceManager
from src.core.errors import AutomationError
from src.models.actions import KEYS

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
                log.info("operation=%s device_id=%s duration_ms=%d result=%s %s", op, did,
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
