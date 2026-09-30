from pydantic import BaseModel


class DeviceStatus(BaseModel):
    id: str
    connected: bool
    serial: str
    android_version: str | None = None
