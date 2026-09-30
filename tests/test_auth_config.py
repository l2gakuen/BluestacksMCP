import pytest

from src.config import ClientConfig, Settings
from src.core.errors import AutomationError
from src.security.auth import authenticate, authorize


def s(**kw):
    return Settings(api_token="secret", **kw)


def test_auth_ok_and_fail():
    assert authenticate(s(), "Bearer secret") == "default"
    for h in (None, "secret", "Bearer nope"):
        with pytest.raises(AutomationError) as e:
            authenticate(s(), h)
        assert e.value.code == "AUTHENTICATION_FAILED"


def test_production_requires_token():
    with pytest.raises(ValueError):
        Settings(production=True)


def test_authorize_restricts():
    st = s(clients={"a": ClientConfig(devices=["d1"], tools=["t1"])})
    authorize(st, "a", "d1", "t1")
    with pytest.raises(AutomationError):
        authorize(st, "a", "d2", "t1")
    with pytest.raises(AutomationError):
        authorize(st, "a", "d1", "t2")


def test_duplicate_devices_rejected():
    d = {"id": "a", "adb_endpoint": "x:1"}
    with pytest.raises(ValueError):
        Settings(devices=[d, d])
