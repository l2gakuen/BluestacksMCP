from __future__ import annotations

import subprocess
from typing import Callable

from src.core.errors import AutomationError

# runner(argv, timeout_s) -> (returncode, stdout_bytes, stderr_bytes); injectable for tests
Runner = Callable[[list[str], float], tuple[int, bytes, bytes]]


def subprocess_runner(argv: list[str], timeout: float) -> tuple[int, bytes, bytes]:
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        raise AutomationError("TIMEOUT", f"ADB command timed out after {timeout:.1f}s.")
    except FileNotFoundError:
        raise AutomationError("ADB_ERROR", "ADB binary not found.", {"binary": argv[0]})
    return p.returncode, p.stdout, p.stderr


class Adb:
    """Thin ADB wrapper. Always argv arrays, never a shell string."""

    def __init__(self, binary: str = "adb", runner: Runner = subprocess_runner):
        self.binary = binary
        self.runner = runner

    def _run(self, args: list[str], timeout: float, serial: str | None = None) -> bytes:
        argv = [self.binary] + (["-s", serial] if serial else []) + args
        rc, out, err = self.runner(argv, timeout)
        if rc != 0:
            raise AutomationError("ADB_ERROR", err.decode(errors="replace").strip() or "adb failed.",
                                  {"args": args})
        return out

    def connect(self, endpoint: str, timeout: float = 10) -> str:
        out = self._run(["connect", endpoint], timeout).decode(errors="replace")
        if "connected" not in out.lower() or "cannot" in out.lower() or "failed" in out.lower():
            raise AutomationError("DEVICE_OFFLINE", out.strip(), {"endpoint": endpoint})
        return out.strip()

    def disconnect(self, endpoint: str, timeout: float = 10) -> None:
        self._run(["disconnect", endpoint], timeout)

    def devices(self, timeout: float = 10) -> dict[str, str]:
        out = self._run(["devices"], timeout).decode(errors="replace")
        res = {}
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                res[parts[0]] = parts[1]
        return res

    def shell(self, serial: str, args: list[str], timeout: float) -> str:
        return self._run(["shell", *args], timeout, serial).decode(errors="replace")

    def getprop(self, serial: str, prop: str, timeout: float = 5) -> str:
        return self.shell(serial, ["getprop", prop], timeout).strip()

    def screencap(self, serial: str, timeout: float) -> bytes:
        return self._run(["exec-out", "screencap", "-p"], timeout, serial)
