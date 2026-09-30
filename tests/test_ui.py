import pytest

from src.core.errors import AutomationError

XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="p" content-desc="" clickable="false" enabled="true" bounds="[0,0][1080,1920]">
<node index="0" text="Login" resource-id="com.example:id/login" class="android.widget.Button" package="p" content-desc="" clickable="true" enabled="true" bounds="[100,200][500,300]"/>
<node index="1" text="Login" resource-id="" class="android.widget.TextView" package="p" content-desc="lbl" clickable="false" enabled="true" bounds="[100,400][500,500]"/>
<node index="2" text="Off" resource-id="" class="android.widget.Button" package="p" content-desc="" clickable="true" enabled="false" bounds="[0,600][100,700]"/>
<node index="3" text="hidden" resource-id="" class="x" package="p" content-desc="" clickable="false" enabled="true" bounds="[0,0][0,0]"/>
</node></hierarchy>
UI hierchary dumped to: /dev/tty"""


@pytest.fixture(autouse=True)
def _xml(runner):
    runner.ui_xml = XML


def taps(runner):
    return [c[-3:] for c in runner.calls if "tap" in c]


def test_dump_normalized(core):
    els = core.dump_ui("bs1")["elements"]
    b = [e for e in els if e["text"] == "Login"][0]
    assert b["bounds"] == [100, 200, 500, 300] and b["clickable"] and b["resource_id"].endswith("login")
    assert not [e for e in els if e["text"] == "hidden"][0]["visible"]


def test_click_text_first_match_center(core, runner):
    r = core.click_text("bs1", "Login")
    assert r["action"] == "click_text" and ["input", "tap", "300", "250"] in [c[-4:] for c in runner.calls if "tap" in c]


def test_selector_priority_index_and_class(core, runner):
    core.click_element("bs1", {"class_name": "android.widget.TextView", "text": "Login"})
    assert any(c[-2:] == ["300", "450"] for c in runner.calls if "tap" in c)
    core.click_element("bs1", {"text": "Login", "index": 1})
    assert core.find_element("bs1", {"content_desc": "lbl"})["element"]["bounds"][1] == 400


def test_errors(core):
    with pytest.raises(AutomationError) as e:
        core.click_text("bs1", "Nope")
    assert e.value.code == "ELEMENT_NOT_FOUND"
    with pytest.raises(AutomationError) as e:
        core.click_text("bs1", "Off")
    assert e.value.code == "ELEMENT_NOT_CLICKABLE"
    with pytest.raises(AutomationError) as e:
        core.find_element("bs1", {})
    assert e.value.code == "INVALID_SELECTOR"
    with pytest.raises(AutomationError) as e:
        core.wait_for_text("bs1", "Nope", 100)
    assert e.value.code == "TIMEOUT"


def test_wait_and_set_text(core, runner):
    assert core.wait_for_text("bs1", "Login", 200)["success"]
    core.set_text("bs1", {"resource_id": "com.example:id/login"}, "hi")
    sh = [c[c.index("shell") + 1:] for c in runner.calls if "shell" in c]
    assert ["input", "keyevent", "123", "67", "67", "67", "67", "67"] in sh and ["input", "text", "hi"] in sh
