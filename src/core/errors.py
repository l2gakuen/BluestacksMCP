from __future__ import annotations

from typing import Any

HTTP_STATUS = {
    "AUTHENTICATION_FAILED": 401,
    "DEVICE_NOT_FOUND": 404,
    "DEVICE_OFFLINE": 503,
    "ADB_ERROR": 502,
    "UI_AUTOMATION_ERROR": 502,
    "ELEMENT_NOT_FOUND": 404,
    "ELEMENT_NOT_CLICKABLE": 409,
    "TIMEOUT": 504,
    "INVALID_SELECTOR": 400,
    "INVALID_ACTION": 400,
    "APP_NOT_FOUND": 404,
    "FORBIDDEN": 403,
    "INTERNAL_ERROR": 500,
}


class AutomationError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def status(self) -> int:
        return HTTP_STATUS.get(self.code, 500)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}
