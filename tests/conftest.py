import pytest

from src.adapters.adb import Adb
from src.config import Settings
from src.core.automation import AutomationCore

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (1080).to_bytes(4, "big") + (1920).to_bytes(4, "big") + b"rest"


class FakeRunner:
    """Records argv; answers adb commands from a small script."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.online = True
        self.ui_xml = ""
        self.packages = {"com.example.app"}

    def __call__(self, argv, timeout):
        self.calls.append(argv)
        a = argv[1:]
        if a[0] == "-s":
            a = a[2:]
        if a == ["devices"]:
            s = "127.0.0.1:5555\tdevice" if self.online else ""
            return 0, f"List of devices attached\n{s}\n".encode(), b""
        if a[0] == "connect":
            return 0, b"connected to 127.0.0.1:5555" if self.online else b"failed to connect", b""
        if a[:2] == ["exec-out", "screencap"]:
            return 0, PNG, b""
        if a[:3] == ["shell", "getprop", "ro.build.version.release"]:
            return 0, b"11\n", b""
        if a[:2] == ["shell", "pm"]:
            pkg = a[-1]
            return 0, (f"package:/data/{pkg}/base.apk".encode() if pkg in self.packages else b""), b""
        if a[:2] == ["shell", "uiautomator"]:
            return 0, b"UI hierchary dumped to: /sdcard/window_dump.xml", b""
        if a[:2] == ["shell", "cat"]:
            return 0, self.ui_xml.encode(), b""
        return 0, b"", b""


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def settings():
    return Settings(api_token="secret", devices=[{"id": "bs1", "adb_endpoint": "127.0.0.1:5555"}])


@pytest.fixture
def core(settings, runner):
    return AutomationCore(settings, Adb("adb", runner))
