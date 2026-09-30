from __future__ import annotations

import hmac

from src.config import Settings
from src.core.errors import AutomationError


def authenticate(settings: Settings, header: str | None) -> str:
    """Validate 'Bearer <token>'; return client name ('default' for the global token)."""
    if not header or not header.startswith("Bearer "):
        raise AutomationError("AUTHENTICATION_FAILED", "Missing bearer token.")
    token = header[7:].strip()
    if settings.api_token and hmac.compare_digest(token.encode(), settings.api_token.encode()):
        return "default"
    for t, name in settings.client_tokens.items():
        if hmac.compare_digest(token.encode(), t.encode()):
            return name
    raise AutomationError("AUTHENTICATION_FAILED", "Invalid token.")


def authorize(settings: Settings, client: str, device_id: str | None, tool: str | None) -> None:
    c = settings.clients.get(client)
    if c is None:
        return
    if device_id and c.devices and device_id not in c.devices:
        raise AutomationError("FORBIDDEN", "Client may not access this device.")
    if tool and c.tools and tool not in c.tools:
        raise AutomationError("FORBIDDEN", "Client may not use this tool.")
