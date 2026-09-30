from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator


class DeviceConfig(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    adb_endpoint: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")


class ClientConfig(BaseModel):
    devices: list[str] = []  # empty = all
    tools: list[str] = []  # empty = all


class Settings(BaseModel):
    bind_host: str = "127.0.0.1"
    rest_port: int = 8000
    mcp_port: int = 8001
    api_token: str = ""
    adb_binary: str = "adb"
    log_level: str = "INFO"
    screenshot_max_size_mb: int = 10
    action_timeout_ms: int = 10000
    ui_wait_timeout_ms: int = 10000
    production: bool = False
    devices: list[DeviceConfig] = []
    enabled_tools: list[str] = []
    clients: dict[str, ClientConfig] = {}
    client_tokens: dict[str, str] = {}  # token -> client name (from clients.<n>.token)

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        ids = [d.id for d in self.devices]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate device ids")
        if self.production and not self.api_token:
            raise ValueError("AUTOMATION_API_TOKEN required in production")
        return self


def load_settings(env_file: str | None = ".env") -> Settings:
    if env_file:
        load_dotenv(env_file)
    e = os.environ
    cfg_path = Path(e.get("CONFIG_FILE", "config.yaml"))
    raw = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    raw = raw or {}
    clients = {}
    tokens = {}
    for name, c in (raw.get("clients") or {}).items():
        c = dict(c)
        tok = c.pop("token", None) or e.get(f"CLIENT_TOKEN_{name.upper().replace('-', '_')}")
        clients[name] = ClientConfig(**c)
        if tok:
            tokens[tok] = name
    return Settings(
        bind_host=e.get("BIND_HOST", "127.0.0.1"),
        rest_port=int(e.get("REST_PORT", 8000)),
        mcp_port=int(e.get("MCP_PORT", 8001)),
        api_token=e.get("AUTOMATION_API_TOKEN", ""),
        adb_binary=e.get("ADB_BINARY", "adb"),
        log_level=e.get("LOG_LEVEL", "INFO"),
        screenshot_max_size_mb=int(e.get("SCREENSHOT_MAX_SIZE_MB", 10)),
        action_timeout_ms=int(e.get("ACTION_TIMEOUT_MS", 10000)),
        ui_wait_timeout_ms=int(e.get("UI_WAIT_TIMEOUT_MS", 10000)),
        production=e.get("PRODUCTION", "").lower() in ("1", "true", "yes"),
        devices=[DeviceConfig(**d) for d in raw.get("devices", [])],
        enabled_tools=(raw.get("mcp") or {}).get("enabled_tools", []) or [],
        clients=clients,
        client_tokens=tokens,
    )
