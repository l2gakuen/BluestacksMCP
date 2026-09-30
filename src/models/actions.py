from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

TIMEOUT = Field(default=None, ge=100, le=60000)
KEYS = ("BACK", "HOME", "ENTER", "TAB", "ESC", "DEL", "MENU", "APP_SWITCH",
        "VOLUME_UP", "VOLUME_DOWN", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT")
Key = Literal[KEYS]  # type: ignore[valid-type]
PKG = r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$"


class Selector(BaseModel):
    text: str | None = None
    resource_id: str | None = None
    content_desc: str | None = None
    class_name: str | None = None
    index: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _nonempty(self):
        if not any((self.text, self.resource_id, self.content_desc, self.class_name)):
            raise ValueError("selector needs at least one of text/resource_id/content_desc/class_name")
        return self


class Tap(BaseModel):
    x: int = Field(ge=0, le=20000)
    y: int = Field(ge=0, le=20000)


class LongPress(Tap):
    duration_ms: int = Field(default=1000, ge=100, le=10000)


class Swipe(BaseModel):
    x1: int = Field(ge=0, le=20000)
    y1: int = Field(ge=0, le=20000)
    x2: int = Field(ge=0, le=20000)
    y2: int = Field(ge=0, le=20000)
    duration_ms: int = Field(default=300, ge=50, le=10000)


class TypeText(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class Press(BaseModel):
    key: Key


class AppReq(BaseModel):
    package: str = Field(pattern=PKG, max_length=255)


class ClickReq(BaseModel):
    text: str | None = None
    selector: Selector | None = None
    timeout_ms: int | None = TIMEOUT

    @model_validator(mode="after")
    def _one(self):
        if (self.text is None) == (self.selector is None):
            raise ValueError("provide exactly one of text or selector")
        return self


class SetTextReq(BaseModel):
    selector: Selector
    text: str = Field(max_length=2000)
    timeout_ms: int | None = TIMEOUT


class WaitText(BaseModel):
    text: str = Field(min_length=1)
    timeout_ms: int | None = TIMEOUT


class WaitElement(BaseModel):
    selector: Selector
    timeout_ms: int | None = TIMEOUT
