from __future__ import annotations

import threading

from src.adapters.adb import Adb
from src.config import Settings
from src.core.errors import AutomationError
from src.models.device import DeviceStatus


class DeviceManager:
    def __init__(self, settings: Settings, adb: Adb):
        self.s = settings
        self.adb = adb
        self._eps = {d.id: d.adb_endpoint for d in settings.devices}
        self.locks = {d.id: threading.RLock() for d in settings.devices}

    def resolve(self, device_id: str | None) -> str:
        if device_id is None:
            if len(self._eps) == 1:
                return next(iter(self._eps))
            raise AutomationError("DEVICE_NOT_FOUND", "device_id required when multiple/no devices configured.",
                                  {"configured": list(self._eps)})
        if device_id not in self._eps:
            raise AutomationError("DEVICE_NOT_FOUND", f"Unknown device '{device_id}'.",
                                  {"configured": list(self._eps)})
        return device_id

    def serial(self, device_id: str) -> str:
        return self._eps[device_id]

    def _is_online(self, device_id: str) -> bool:
        try:
            return self.adb.devices().get(self._eps[device_id]) == "device"
        except AutomationError:
            return False

    def connect(self, device_id: str) -> DeviceStatus:
        device_id = self.resolve(device_id)
        self.adb.connect(self._eps[device_id])
        return self.status(device_id)

    def disconnect(self, device_id: str) -> DeviceStatus:
        device_id = self.resolve(device_id)
        self.adb.disconnect(self._eps[device_id])
        return self.status(device_id)

    def status(self, device_id: str | None) -> DeviceStatus:
        device_id = self.resolve(device_id)
        ep = self._eps[device_id]
        online = self._is_online(device_id)
        ver = None
        if online:
            try:
                ver = self.adb.getprop(ep, "ro.build.version.release") or None
            except AutomationError:
                ver = None
        return DeviceStatus(id=device_id, connected=online, serial=ep, android_version=ver)

    def list(self) -> list[DeviceStatus]:
        return [self.status(i) for i in self._eps]

    def ensure_online(self, device_id: str | None) -> tuple[str, str]:
        """Verify the device is connected (auto-connect once) and return (id, serial)."""
        device_id = self.resolve(device_id)
        if not self._is_online(device_id):
            try:
                self.adb.connect(self._eps[device_id])
            except AutomationError:
                pass
            if not self._is_online(device_id):
                raise AutomationError("DEVICE_OFFLINE", f"Device '{device_id}' is offline.",
                                      {"device_id": device_id})
        return device_id, self._eps[device_id]
