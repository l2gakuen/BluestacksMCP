import pytest
from fastapi.testclient import TestClient

from src.server.rest import create_app
from tests.test_ui import XML

H = {"Authorization": "Bearer secret"}


@pytest.fixture
def client(core, settings, runner):
    runner.ui_xml = XML
    return TestClient(create_app(core, settings), raise_server_exceptions=False)


def test_health_open_others_require_auth(client):
    assert client.get("/health").json()["status"] == "ok"
    for path in ("/api/v1/devices", "/api/v1/devices/bs1/ui", "/api/v1/devices/bs1/screenshot",
                 "/api/v1/health/devices", "/api/v1/devices/bs1"):
        r = client.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "AUTHENTICATION_FAILED"
    assert client.post("/api/v1/devices/bs1/actions/tap", json={"x": 1, "y": 1},
                       headers={"Authorization": "Bearer bad"}).status_code == 401


def test_devices_and_screenshot(client):
    assert client.get("/api/v1/devices", headers=H).json()[0]["id"] == "bs1"
    r = client.get("/api/v1/devices/bs1/screenshot", headers=H)
    assert r.headers["content-type"] == "image/png" and r.content.startswith(b"\x89PNG")
    assert client.get("/api/v1/devices/nope", headers=H).status_code == 404


def test_actions(client):
    assert client.post("/api/v1/devices/bs1/actions/tap", json={"x": 5, "y": 6}, headers=H).json()["success"]
    assert client.post("/api/v1/devices/bs1/actions/click", json={"text": "Login"}, headers=H).json()["target"] == "Login"
    assert client.post("/api/v1/devices/bs1/actions/press", json={"key": "BACK"}, headers=H).status_code == 200
    r = client.post("/api/v1/devices/bs1/actions/click", json={"selector": {"text": "zzz"}}, headers=H)
    assert r.status_code == 404 and r.json()["error"]["code"] == "ELEMENT_NOT_FOUND"


def test_validation_and_limits(client):
    r = client.post("/api/v1/devices/bs1/actions/press", json={"key": "rm"}, headers=H)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_ACTION"
    r = client.post("/api/v1/devices/bs1/actions/type", content=b"x" * 70000, headers={**H, "content-type": "application/json"})
    assert r.status_code == 413


def test_request_id(client):
    assert client.get("/health", headers={"X-Request-ID": "abcdefgh1234"}).headers["x-request-id"] == "abcdefgh1234"
    assert len(client.get("/health", headers={"X-Request-ID": "bad id!"}).headers["x-request-id"]) == 32
