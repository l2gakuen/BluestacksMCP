"""Run from the install folder: .\.venv\Scripts\python.exe scripts\check_auth.py
Shows which API token the service would load (never the full token)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_settings  # noqa: E402

print("cwd:", Path.cwd())
print(".env in cwd:", Path(".env").exists())
env = os.environ.get("AUTOMATION_API_TOKEN")
print("Windows env var AUTOMATION_API_TOKEN set:", bool(env), "(overrides .env!)" if env else "")
t = load_settings().api_token
print(f"loaded token: length={len(t)} first4={t[:4]!r} last4={t[-4:]!r}")
if t != t.strip() or any(c in t for c in " \r\n\"'"):
    print("WARNING: token contains whitespace or quotes")
