# BlueStacks Remote Android Automation Node

REST (`:8000`) and MCP (`:8001`) servers over one `AutomationCore` (ADB + UIAutomator dump), meant to be
reached over ZeroTier. See `spec.md` for the design and `TODO.md` for progress.

## Setup (Windows)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # set AUTOMATION_API_TOKEN, ADB_BINARY, BIND_HOST
copy config.example.yaml config.yaml
.venv\Scripts\python.exe -m src.main
```

Enable ADB in BlueStacks (Settings > Advanced > Android Debug Bridge) and put its port in `config.yaml`.
Generate a token: `python -c "import secrets;print(secrets.token_urlsafe(48))"`.

## ZeroTier: no reverse proxy needed

ZeroTier gives the Windows host a virtual adapter with a private IP (e.g. `10.147.0.20`).
Clients on the same ZeroTier network reach it directly; traffic is already end-to-end encrypted.

1. Install ZeroTier on the Windows host and the client, join the same network ID, authorize both in
   ZeroTier Central. Get the host IP: `ipconfig` (adapter "ZeroTier One ...") or Central.
2. In `.env` set `BIND_HOST=10.147.0.20` (the host's ZeroTier IP, **not** `0.0.0.0`).
   BlueStacks ADB stays on `127.0.0.1`; it is never exposed.
3. Firewall (PowerShell, admin; replace the subnet with yours):

```powershell
New-NetFirewallRule -DisplayName "Automation ZeroTier" -Direction Inbound -Protocol TCP `
  -LocalPort 8000,8001 -RemoteAddress 10.147.0.0/16 -Action Allow
```
   Nothing else allows these ports, so public interfaces stay blocked (binding to the ZeroTier IP
   already means they don't listen there).
4. From the client:

```bash
curl -H "Authorization: Bearer $TOKEN" http://10.147.0.20:8000/api/v1/devices
```

MCP client config (streamable HTTP): `http://10.147.0.20:8001/mcp` with header `Authorization: Bearer <token>`.
Claude Code: `claude mcp add --transport http android http://10.147.0.20:8001/mcp --header "Authorization: Bearer $TOKEN"`.

A reverse proxy (Caddy/nginx) is only useful if you want TLS or a single port; if you add one, keep it
bound to the ZeroTier IP too. For a Windows service, wrap `python -m src.main` with NSSM.

## MCP tools

`android_list_devices, device_status, list_apps, current_app, launch_app, stop_app, dump_ui,
extract_text, find_text, find_element, screenshot, wait_for_text, wait_for_element, tap, long_press,
swipe, scroll, pull_to_refresh, click_text, click_element, type, set_text, press`.
Restrict with `mcp.enabled_tools` in `config.yaml`; per-client device/tool limits via `clients:`.

## REST

`GET /health`, `GET /api/v1/health/devices`, `GET /api/v1/devices[/{id}]`, `.../screenshot`, `.../ui`, `.../apps`,
`.../app`, `POST .../actions/{tap,long_press,swipe,type,press,click,set_text,scroll,pull_to_refresh,launch_app,stop_app}`,
`POST .../wait/{text,element}`, `POST .../extract`, `POST .../find`, `POST .../workflows`. Docs at `/api/docs`.

## Tests

`pytest` (unit tests use a fake ADB runner). Integration tests need a real BlueStacks (not automated yet).

## Known gaps

- UI inspection uses `adb shell uiautomator dump`, not the uiautomator2 on-device server.
- Workflows run synchronously (max 50 steps); no async job/status API yet.
- No TLS, Prometheus metrics, or Windows-service installer.

## Offline bundle

`python scripts/package.py --python 3.11 [--with-adb]` builds `dist/bluestacks-automation.zip` (source + win_amd64
wheels + `install.ps1`). `--python` must match the Python minor version on the Windows host.
On Windows: unzip, then `powershell -ExecutionPolicy Bypass -File install.ps1` (creates `.venv`, installs offline,
generates the API token in `.env`). Then edit `BIND_HOST` and `config.yaml` and run `python -m src.main`.
