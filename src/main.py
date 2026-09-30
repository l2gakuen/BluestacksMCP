from __future__ import annotations

import asyncio
import logging
import shutil
import socket
import sys

import uvicorn

from src.config import Settings, load_settings
from src.core.automation import AutomationCore
from src.server.mcp import create_mcp_app
from src.server.rest import create_app


def preflight(s: Settings) -> None:
    """Fail closed on misconfiguration (spec §33)."""
    problems = []
    if not s.api_token and not s.client_tokens:
        problems.append("no authentication configured (AUTOMATION_API_TOKEN)")
    if not shutil.which(s.adb_binary):
        problems.append(f"ADB binary not found: {s.adb_binary}")
    if not s.devices:
        problems.append("no devices configured (config.yaml)")
    for port in (s.rest_port, s.mcp_port):
        with socket.socket() as sock:
            try:
                sock.bind((s.bind_host, port))
            except OSError as e:
                problems.append(f"cannot bind {s.bind_host}:{port}: {e}")
    if problems:
        sys.exit("Startup failed:\n - " + "\n - ".join(problems))


async def serve(s: Settings) -> None:
    core = AutomationCore(s)
    for d in s.devices:  # best-effort connect; requests re-verify anyway
        try:
            core.connect(d.id)
        except Exception as e:
            logging.getLogger("startup").warning("device %s not connected: %s", d.id, getattr(e, "message", e))
    cfgs = [uvicorn.Config(create_app(core, s), host=s.bind_host, port=s.rest_port, log_level=s.log_level.lower()),
            uvicorn.Config(create_mcp_app(core, s), host=s.bind_host, port=s.mcp_port, log_level=s.log_level.lower())]
    await asyncio.gather(*(uvicorn.Server(c).serve() for c in cfgs))


def main() -> None:
    s = load_settings()
    logging.basicConfig(level=s.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    preflight(s)
    asyncio.run(serve(s))


if __name__ == "__main__":
    main()
