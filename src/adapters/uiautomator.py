from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

from src.adapters.adb import Adb
from src.core.errors import AutomationError

_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def parse_hierarchy(xml: str) -> list[dict]:
    """Normalize UIAutomator XML into a flat list of stable-JSON elements (document order)."""
    end = xml.find("</hierarchy>")
    start = xml.find("<?xml")
    if end < 0 or start < 0:
        raise AutomationError("UI_AUTOMATION_ERROR", "UI dump returned no hierarchy.")
    try:
        root = ET.fromstring(xml[start:end + len("</hierarchy>")])
    except ET.ParseError as e:
        raise AutomationError("UI_AUTOMATION_ERROR", f"Malformed UI dump: {e}")
    out = []
    for n in root.iter("node"):
        m = _BOUNDS.fullmatch(n.get("bounds", ""))
        b = [int(g) for g in m.groups()] if m else [0, 0, 0, 0]
        out.append({
            "text": n.get("text", ""),
            "content_desc": n.get("content-desc", ""),
            "resource_id": n.get("resource-id", ""),
            "class_name": n.get("class", ""),
            "package": n.get("package", ""),
            "clickable": n.get("clickable") == "true",
            "enabled": n.get("enabled") == "true",
            "visible": b[2] > b[0] and b[3] > b[1],
            "bounds": b,
        })
    return out


class UiAutomator:
    """UIAutomator via ADB (`uiautomator dump`). Swap this class to use the uiautomator2 on-device server."""

    def __init__(self, adb: Adb):
        self.adb = adb

    DUMP_PATH = "/sdcard/window_dump.xml"
    ATTEMPTS = 3  # dump is flaky on busy/animated screens (empty output or timeout): retry

    def dump(self, serial: str, timeout: float) -> list[dict]:
        # Dump to a file then cat it: `dump /dev/tty` returns nothing on some Android versions.
        last: AutomationError | None = None
        for attempt in range(self.ATTEMPTS):
            if attempt:
                time.sleep(1.0)
            try:
                msg = self.adb.shell(serial, ["uiautomator", "dump", self.DUMP_PATH], timeout).strip()
                if "dumped to" not in msg:
                    raise AutomationError("UI_AUTOMATION_ERROR", "UiAutomator could not dump the screen.",
                                          {"device_output": msg[:300]})
                return parse_hierarchy(self.adb.shell(serial, ["cat", self.DUMP_PATH], timeout))
            except AutomationError as e:
                if e.code not in ("UI_AUTOMATION_ERROR", "TIMEOUT"):
                    raise
                last = e
        raise last  # type: ignore[misc]
