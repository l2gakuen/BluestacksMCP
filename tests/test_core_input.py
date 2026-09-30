import pytest

from src.config import Settings
from src.core.automation import AutomationCore, _input_escape
from src.core.errors import AutomationError


def shell_calls(runner):
    return [c[c.index("shell") + 1:] for c in runner.calls if "shell" in c]


def test_tap_uses_argv_and_serial(core, runner):
    r = core.tap(None, 10, 20)
    assert r["success"] and r["device_id"] == "bs1"
    assert ["input", "tap", "10", "20"] in shell_calls(runner)
    assert ["-s", "127.0.0.1:5555"] == [c for c in runner.calls if "tap" in c][0][1:3]


def test_type_escapes_and_never_returns_text(core, runner):
    r = core.type_text("bs1", "a b;rm -rf /")
    assert "rm" not in str(r)
    assert ["input", "text", r"a%sb\;rm%s-rf%s/"] in shell_calls(runner)


def test_escape():
    assert _input_escape("hi there$") == "hi%sthere\\$"


def test_press_invalid(core):
    with pytest.raises(AutomationError) as e:
        core.press("bs1", "NOPE")
    assert e.value.code == "INVALID_ACTION"


def test_unknown_and_ambiguous_device(core, settings):
    with pytest.raises(AutomationError) as e:
        core.tap("zzz", 1, 1)
    assert e.value.code == "DEVICE_NOT_FOUND"
    two = Settings(devices=[{"id": "a", "adb_endpoint": "x:1"}, {"id": "b", "adb_endpoint": "x:2"}])
    with pytest.raises(AutomationError):
        AutomationCore(two).dm.resolve(None)


def test_offline(core, runner):
    runner.online = False
    with pytest.raises(AutomationError) as e:
        core.tap("bs1", 1, 1)
    assert e.value.code == "DEVICE_OFFLINE"


def test_screenshot_and_size(core):
    png = core.screenshot("bs1")
    assert core.png_size(png) == (1080, 1920)


def test_apps(core, runner):
    core.launch_app("bs1", "com.example.app")
    with pytest.raises(AutomationError) as e:
        core.launch_app("bs1", "com.missing.app")
    assert e.value.code == "APP_NOT_FOUND"


def test_status(core):
    st = core.get_device("bs1")
    assert st.connected and st.android_version == "11"
