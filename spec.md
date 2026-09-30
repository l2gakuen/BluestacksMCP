# BlueStacks Remote Android Automation Node — Specification

## 1. Purpose

Build a Windows-hosted automation service that controls one or more BlueStacks Android instances remotely over a ZeroTier network.

The system exposes **both**:

1. A REST/HTTP API for deterministic programmatic control.
2. An MCP server for AI-agent/tool-based control.

Both interfaces MUST use the same underlying automation core so behavior is consistent.

```text
                         ZeroTier Network
                               │
              ┌────────────────┴────────────────┐
              │                                 │
        REST client                         MCP client
              │                                 │
              └──────────────┬──────────────────┘
                             │
                    Windows Automation Node
                             │
                  ┌──────────▼──────────┐
                  │  API / MCP Gateway  │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │ Automation Core     │
                  │                    │
                  │ ADB                │
                  │ UIAutomator2       │
                  │ Screenshot         │
                  │ Device Manager      │
                  └──────────┬──────────┘
                             │
                    ┌────────▼────────┐
                    │    BlueStacks   │
                    │     Android     │
                    └─────────────────┘
```

## 2. Goals

### Required

- Run on Windows.
- Control BlueStacks through ADB.
- Support UIAutomator2 for semantic UI interaction.
- Support screenshots.
- Support UI hierarchy inspection.
- Support coordinate-based input when semantic interaction is unavailable.
- Expose REST API.
- Expose MCP tools.
- Bind network services to the ZeroTier interface or otherwise restrict access to ZeroTier peers.
- Authenticate remote requests.
- Support multiple BlueStacks instances where possible.
- Return structured errors.
- Provide health/status endpoints.
- Provide logging and audit information.
- Keep REST and MCP behavior backed by the same Python automation library.

### Non-goals

- Public Internet exposure.
- Circumventing application security controls.
- Automating systems where the operator does not have authorization.
- Replacing Android's security model.
- Implementing an arbitrary remote desktop protocol.

## 3. Technology Stack

Recommended implementation:

| Component | Technology |
|---|---|
| Host | Windows 10/11 |
| Android runtime | BlueStacks |
| Device transport | ADB |
| UI automation | UIAutomator2 |
| Core language | Python 3.11+ |
| REST | FastAPI |
| MCP | MCP Python SDK |
| Validation | Pydantic |
| HTTP server | Uvicorn |
| Network | ZeroTier |
| Configuration | `.env` + YAML/JSON |
| Logging | Python `logging` |
| Tests | pytest |

The implementation SHOULD isolate BlueStacks-specific behavior behind an adapter so another Android emulator can be supported later.

## 4. High-Level Components

```text
src/
├── server/
│   ├── rest.py
│   └── mcp.py
├── core/
│   ├── automation.py
│   ├── device_manager.py
│   ├── selectors.py
│   ├── screenshots.py
│   └── errors.py
├── adapters/
│   ├── adb.py
│   └── uiautomator.py
├── models/
│   ├── device.py
│   ├── actions.py
│   └── responses.py
├── security/
│   └── auth.py
├── config.py
└── main.py
```

Both servers call:

```text
AutomationCore
```

and MUST NOT independently implement ADB/UIAutomator logic.

## 5. BlueStacks / ADB

The Windows host MUST have ADB available.

The automation service SHOULD discover configured BlueStacks ADB endpoints rather than assuming a single hard-coded endpoint.

Typical configuration:

```yaml
devices:
  - id: bluestacks-1
    adb_endpoint: 127.0.0.1:5555
```

If BlueStacks exposes another ADB port, that port MUST be configurable.

The service SHOULD support:

```text
adb connect <endpoint>
adb devices
adb shell ...
```

The service MUST verify the connected device before performing actions.

## 6. Device Abstraction

Every operation accepts an optional `device_id`.

Example:

```json
{
  "device_id": "bluestacks-1"
}
```

If only one device is configured, `device_id` MAY be omitted.

Device status:

```json
{
  "id": "bluestacks-1",
  "connected": true,
  "serial": "127.0.0.1:5555",
  "android_version": "..."
}
```

## 7. Automation Core

The automation core provides the canonical operations.

### Device

```text
list_devices()
get_device(device_id)
device_status(device_id)
connect(device_id)
disconnect(device_id)
```

### Application

```text
launch_app(device_id, package)
stop_app(device_id, package)
current_app(device_id)
```

### Input

```text
tap(device_id, x, y)
long_press(device_id, x, y, duration_ms)
swipe(device_id, x1, y1, x2, y2, duration_ms)
type_text(device_id, text)
press(device_id, key)
```

### Semantic UI

```text
dump_ui(device_id)
find_text(device_id, text)
click_text(device_id, text)
find_element(device_id, selector)
click_element(device_id, selector)
set_text(device_id, selector, text)
wait_for_text(device_id, text, timeout_ms)
wait_for_element(device_id, selector, timeout_ms)
```

### Visual

```text
screenshot(device_id)
```

Screenshots SHOULD be returned as PNG.

## 8. Selector Model

Selectors SHOULD support:

```json
{
  "text": "Login"
}
```

```json
{
  "resource_id": "com.example:id/login"
}
```

```json
{
  "content_desc": "Login"
}
```

```json
{
  "class_name": "android.widget.Button",
  "text": "Login"
}
```

The implementation MAY support a richer selector:

```json
{
  "text": "Login",
  "resource_id": "com.example:id/login",
  "class_name": "android.widget.Button",
  "index": 0
}
```

Selectors SHOULD be evaluated in a deterministic order.

## 9. REST API

Base path:

```text
/api/v1
```

### Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### Devices

```http
GET /api/v1/devices
GET /api/v1/devices/{device_id}
```

### Screenshot

```http
GET /api/v1/devices/{device_id}/screenshot
```

Response:

```text
image/png
```

### UI hierarchy

```http
GET /api/v1/devices/{device_id}/ui
```

Response:

```json
{
  "device_id": "bluestacks-1",
  "elements": [
    {
      "text": "Login",
      "resource_id": "com.example:id/login",
      "class_name": "android.widget.Button",
      "clickable": true,
      "bounds": [100, 200, 500, 300]
    }
  ]
}
```

### Tap

```http
POST /api/v1/devices/{device_id}/actions/tap
```

Request:

```json
{
  "x": 500,
  "y": 700
}
```

### Text input

```http
POST /api/v1/devices/{device_id}/actions/type
```

Request:

```json
{
  "text": "hello world"
}
```

### Semantic click

```http
POST /api/v1/devices/{device_id}/actions/click
```

Request:

```json
{
  "text": "Login"
}
```

or:

```json
{
  "selector": {
    "resource_id": "com.example:id/login"
  }
}
```

### Swipe

```http
POST /api/v1/devices/{device_id}/actions/swipe
```

Request:

```json
{
  "x1": 500,
  "y1": 1200,
  "x2": 500,
  "y2": 400,
  "duration_ms": 500
}
```

### Press

```http
POST /api/v1/devices/{device_id}/actions/press
```

Request:

```json
{
  "key": "BACK"
}
```

Supported keys SHOULD include:

```text
BACK
HOME
ENTER
TAB
ESC
```

### Wait

```http
POST /api/v1/devices/{device_id}/wait/text
```

Request:

```json
{
  "text": "Login successful",
  "timeout_ms": 10000
}
```

## 10. REST Authentication

Every non-health API endpoint MUST require authentication.

Recommended initial design:

```http
Authorization: Bearer <API_TOKEN>
```

The token MUST be stored outside source control.

Example:

```env
AUTOMATION_API_TOKEN=replace-with-long-random-secret
```

Authentication SHOULD use constant-time token comparison.

The service MUST NOT log bearer tokens.

## 11. MCP Server

The MCP server exposes the same AutomationCore methods as tools.

Recommended tools:

```text
android_list_devices
android_device_status
android_screenshot
android_dump_ui
android_tap
android_long_press
android_swipe
android_type
android_press
android_click_text
android_click_element
android_set_text
android_find_text
android_wait_for_text
android_wait_for_element
android_launch_app
android_stop_app
android_current_app
```

### Example MCP tool

```text
android_click_text(
    device_id="bluestacks-1",
    text="Login"
)
```

The tool MUST call:

```text
AutomationCore.click_text(...)
```

rather than executing its own ADB commands.

## 12. MCP Screenshot Behavior

`android_screenshot` SHOULD return an image content block where supported by the MCP client.

The server SHOULD also provide metadata:

```json
{
  "device_id": "bluestacks-1",
  "width": 1080,
  "height": 1920,
  "format": "png"
}
```

The image itself MUST NOT be logged.

## 13. MCP Safety

Destructive or consequential actions SHOULD be represented as explicit tools.

For example:

```text
android_press
android_tap
android_type
```

The MCP tool descriptions SHOULD clearly explain that they cause actions on the remote Android device.

The server SHOULD provide a configurable allowlist of enabled tools.

Example:

```yaml
mcp:
  enabled_tools:
    - android_list_devices
    - android_screenshot
    - android_dump_ui
    - android_click_text
    - android_type
    - android_press
```

## 14. ZeroTier Network

The Windows host MUST join the same ZeroTier network as the remote client.

Example topology:

```text
Client
10.147.0.10
     │
     │ ZeroTier
     │
Windows
10.147.0.20
     │
     ├── REST :8000
     └── MCP  :8001
```

The server SHOULD bind to the Windows host's ZeroTier IP rather than:

```text
0.0.0.0
```

unless firewall rules explicitly restrict access.

Example:

```env
BIND_HOST=10.147.0.20
REST_PORT=8000
MCP_PORT=8001
```

## 15. Windows Firewall

Windows Firewall SHOULD allow inbound connections only from the ZeroTier network/subnet to the configured service ports.

Public WAN access MUST NOT be required.

Recommended policy:

```text
Allow:
    ZeroTier subnet → TCP 8000
    ZeroTier subnet → TCP 8001

Deny:
    Public interfaces → TCP 8000
    Public interfaces → TCP 8001
```

The exact firewall commands depend on the assigned ZeroTier subnet and MUST be configured for the deployment.

## 16. MCP Transport

The MCP implementation SHOULD use a network-capable MCP transport appropriate for the MCP SDK version being deployed.

The transport endpoint MUST be bound to the ZeroTier interface or protected by firewall rules.

The MCP endpoint MUST require authentication.

If the chosen MCP transport uses HTTP, authentication SHOULD use the same bearer-token infrastructure as REST.

## 17. Configuration

Example `.env`:

```env
BIND_HOST=10.147.0.20

REST_PORT=8000
MCP_PORT=8001

AUTOMATION_API_TOKEN=<random-secret>

ADB_BINARY=C:\Android\platform-tools\adb.exe

LOG_LEVEL=INFO

SCREENSHOT_MAX_SIZE_MB=10
ACTION_TIMEOUT_MS=10000
UI_WAIT_TIMEOUT_MS=10000
```

Example device configuration:

```yaml
devices:
  - id: bluestacks-1
    adb_endpoint: 127.0.0.1:5555

  - id: bluestacks-2
    adb_endpoint: 127.0.0.1:5556
```

## 18. Error Model

All REST errors SHOULD use a consistent structure:

```json
{
  "error": {
    "code": "ELEMENT_NOT_FOUND",
    "message": "No element matching the selector was found.",
    "details": {
      "selector": {
        "text": "Login"
      }
    }
  }
}
```

Recommended error codes:

```text
AUTHENTICATION_FAILED
DEVICE_NOT_FOUND
DEVICE_OFFLINE
ADB_ERROR
UI_AUTOMATION_ERROR
ELEMENT_NOT_FOUND
ELEMENT_NOT_CLICKABLE
TIMEOUT
INVALID_SELECTOR
INVALID_ACTION
APP_NOT_FOUND
INTERNAL_ERROR
```

## 19. Logging

Logs SHOULD contain:

```text
timestamp
request_id
device_id
operation
duration_ms
result
error_code
```

Logs MUST NOT contain:

- API tokens
- passwords
- arbitrary sensitive text entered into applications
- screenshot contents

For `type_text`, log only:

```text
operation=type_text
text_length=12
```

not the actual text.

## 20. Request IDs

Every REST request SHOULD receive a request ID.

Example:

```http
X-Request-ID: 7b7f...
```

If the caller supplies one, the server MAY preserve it after validation.

The same ID SHOULD be included in logs.

## 21. Concurrency

A single Android device SHOULD use an action lock.

Example:

```text
request A → device lock → tap → release
request B → waits
```

This prevents two independent clients from simultaneously manipulating the same UI.

Different BlueStacks devices MAY operate concurrently.

```text
bluestacks-1 → lock A
bluestacks-2 → lock B
```

## 22. Action Timeouts

Every action MUST have a timeout.

Default:

```text
10 seconds
```

Configurable globally and per request.

Long-running workflows SHOULD use an explicit workflow/job mechanism rather than holding an HTTP request indefinitely.

## 23. Workflow API

A future-compatible workflow endpoint SHOULD be supported.

Example:

```http
POST /api/v1/devices/bluestacks-1/workflows
```

Request:

```json
{
  "actions": [
    {
      "type": "click_text",
      "text": "Login"
    },
    {
      "type": "type",
      "text": "example"
    },
    {
      "type": "press",
      "key": "ENTER"
    },
    {
      "type": "wait_text",
      "text": "Welcome",
      "timeout_ms": 10000
    }
  ]
}
```

The workflow engine MUST execute actions through AutomationCore.

## 24. Screenshots

Screenshots SHOULD be captured directly from the Android device through ADB/UI automation.

The server MAY optionally save screenshots temporarily for debugging.

Temporary screenshot files MUST:

- have restricted permissions
- have configurable retention
- be deleted automatically
- never be committed to source control

## 25. UI Hierarchy

The UI dump SHOULD normalize platform-specific UIAutomator output into a stable JSON structure.

Example:

```json
{
  "elements": [
    {
      "text": "Username",
      "content_desc": "",
      "resource_id": "com.example:id/username",
      "class_name": "android.widget.EditText",
      "clickable": false,
      "enabled": true,
      "visible": true,
      "bounds": [100, 300, 900, 400]
    }
  ]
}
```

This normalized representation is what REST and MCP clients SHOULD consume.

## 26. Semantic Automation Strategy

Automation SHOULD prefer selectors in this order:

1. Stable resource ID.
2. Accessibility/content description.
3. Exact text.
4. Class + text.
5. Coordinate fallback.

Coordinates SHOULD be the final fallback because they are sensitive to:

- resolution
- orientation
- window size
- scaling
- UI changes

## 27. BlueStacks Window Independence

The automation system SHOULD NOT depend on the BlueStacks window being focused.

ADB/UIAutomator operations SHOULD operate directly against the Android instance whenever possible.

This permits the Windows machine to continue performing other work while automation executes.

## 28. Authentication and Authorization

Initial implementation:

```text
ZeroTier network
        +
Bearer API token
```

Future implementation MAY add:

- per-client API keys
- mTLS
- OAuth/OIDC
- per-device permissions
- per-tool permissions
- audit identities

Authorization SHOULD support restricting a client to specific devices.

Example:

```yaml
clients:
  agent-a:
    devices:
      - bluestacks-1
    tools:
      - android_screenshot
      - android_dump_ui
      - android_click_text
```

## 29. Security Requirements

The implementation MUST:

- authenticate remote requests
- avoid public Internet exposure
- validate all request parameters
- enforce action timeouts
- avoid shell-string interpolation
- invoke ADB using safe argument arrays where possible
- avoid logging secrets
- limit screenshot size
- restrict filesystem access
- restrict enabled MCP tools
- serialize actions per device

The implementation MUST NOT accept arbitrary shell commands as a general-purpose API.

If raw ADB access is added for diagnostics, it MUST be separately authenticated and disabled by default.

## 30. Health Checks

`GET /health` checks only that the server process is alive.

A deeper endpoint SHOULD be provided:

```http
GET /api/v1/health/devices
```

Example:

```json
{
  "status": "ok",
  "devices": {
    "bluestacks-1": {
      "connected": true
    },
    "bluestacks-2": {
      "connected": false
    }
  }
}
```

## 31. Metrics

Optional metrics SHOULD include:

```text
automation_actions_total
automation_action_errors_total
automation_action_duration_seconds
device_connected
device_action_queue_length
```

Prometheus-compatible metrics MAY be exposed on a separate protected endpoint.

## 32. Installation

Recommended directory:

```text
C:\bluestacks-automation\
```

Example:

```text
C:\bluestacks-automation\
├── .env
├── config.yaml
├── pyproject.toml
├── src\
├── tests\
└── logs\
```

Install:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The exact dependency versions MUST be pinned in the production build.

## 33. Startup

Example:

```powershell
.venv\Scripts\python.exe -m src.main
```

The application SHOULD verify on startup:

1. Configuration is valid.
2. ADB executable exists.
3. Configured devices can be discovered.
4. Authentication is configured.
5. The bind address exists on the host.
6. Required ports are available.

Startup SHOULD fail closed if authentication is missing in production mode.

## 34. Windows Service

Production deployment SHOULD run the automation server as a Windows service.

The service SHOULD:

- start automatically
- restart after failure
- run under a dedicated Windows account
- have only required filesystem permissions
- write logs to a controlled directory

## 35. API Documentation

FastAPI SHOULD expose OpenAPI documentation.

Development:

```text
/api/docs
/api/openapi.json
```

Production documentation MAY be disabled or protected.

## 36. MCP Tool Schemas

Every MCP tool MUST have:

- descriptive name
- clear description
- JSON input schema
- device ID parameter
- bounded timeout where relevant
- structured result
- structured error

Example:

```json
{
  "name": "android_click_text",
  "description": "Click an Android UI element matching exact visible text.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "device_id": {
        "type": "string"
      },
      "text": {
        "type": "string"
      },
      "timeout_ms": {
        "type": "integer",
        "minimum": 100,
        "maximum": 60000
      }
    },
    "required": ["device_id", "text"]
  }
}
```

## 37. Example End-to-End Flow

### REST

```text
1. Remote client connects to Windows ZeroTier IP.
2. Client authenticates with bearer token.
3. GET /api/v1/devices
4. POST /api/v1/devices/bluestacks-1/actions/click
5. AutomationCore obtains device lock.
6. UIAutomator2 searches for "Login".
7. Element is clicked.
8. Lock is released.
9. REST returns structured result.
```

### MCP

```text
1. Agent connects to MCP endpoint through ZeroTier.
2. MCP authenticates the client.
3. Agent calls android_dump_ui.
4. Server returns normalized UI hierarchy.
5. Agent decides to click "Login".
6. Agent calls android_click_text.
7. MCP invokes AutomationCore.
8. AutomationCore invokes UIAutomator2.
9. Result is returned to the agent.
10. Agent may request android_screenshot for visual confirmation.
```

## 38. Example Response

Successful action:

```json
{
  "success": true,
  "device_id": "bluestacks-1",
  "action": "click_text",
  "target": "Login",
  "duration_ms": 184
}
```

Failed action:

```json
{
  "success": false,
  "device_id": "bluestacks-1",
  "action": "click_text",
  "error": {
    "code": "ELEMENT_NOT_FOUND",
    "message": "No visible element matched text 'Login'."
  }
}
```

## 39. Testing

### Unit tests

Test:

- selector normalization
- request validation
- authentication
- device locking
- error conversion
- configuration
- action serialization

### Integration tests

On a real BlueStacks installation:

```text
ADB connection
Screenshot
UI dump
Tap
Text input
Semantic click
Swipe
Back
App launch
Wait for element
```

### Security tests

Verify:

- unauthenticated requests fail
- invalid tokens fail
- public interface cannot reach service
- invalid device IDs fail
- arbitrary shell execution is impossible
- oversized requests are rejected
- secrets are absent from logs

## 40. Acceptance Criteria

The implementation is complete when:

- [ ] Windows host runs the service.
- [ ] BlueStacks is controllable through ADB.
- [ ] UIAutomator2 can inspect the UI.
- [ ] Screenshot retrieval works.
- [ ] Semantic click works.
- [ ] Coordinate tap works.
- [ ] Text entry works.
- [ ] Swipe works.
- [ ] Back/home/enter actions work.
- [ ] REST API exposes all core operations.
- [ ] MCP exposes the same core operations.
- [ ] REST and MCP use the same AutomationCore.
- [ ] ZeroTier clients can connect.
- [ ] Non-ZeroTier interfaces are blocked.
- [ ] Authentication is required.
- [ ] Per-device locking works.
- [ ] Errors are structured.
- [ ] Secrets are not logged.
- [ ] Multiple BlueStacks instances can be configured.
- [ ] Automated tests cover the core functionality.

## 41. Recommended Initial Scope

Build in this order:

### Phase 1 — Local Android control

```text
Python
  ↓
ADB
  ↓
BlueStacks
```

Implement:

- device discovery
- screenshot
- tap
- swipe
- type
- press

### Phase 2 — Semantic UI

```text
Python
  ↓
UIAutomator2
  ↓
BlueStacks
```

Implement:

- UI dump
- selectors
- click text
- click element
- set text
- wait for element

### Phase 3 — REST

```text
HTTP
 ↓
FastAPI
 ↓
AutomationCore
```

### Phase 4 — MCP

```text
MCP
 ↓
AutomationCore
```

### Phase 5 — Remote networking

```text
ZeroTier
 ↓
Windows automation node
```

Add:

- firewall rules
- authentication
- TLS if required by the deployment
- audit logging

### Phase 6 — Multi-device and workflows

Add:

- multiple BlueStacks instances
- per-device queues
- workflow execution
- job status
- stronger authorization

## 42. Final Architecture

The final system SHOULD look like:

```text
                     ┌─────────────────────┐
                     │ Remote AI / Client  │
                     └──────────┬──────────┘
                                │
                         ZeroTier VPN
                                │
               ┌────────────────▼────────────────┐
               │        Windows Host             │
               │                                 │
               │  ┌──────────┐   ┌───────────┐  │
               │  │ REST API │   │ MCP Server│  │
               │  └────┬─────┘   └─────┬─────┘  │
               │       └───────┬───────┘        │
               │               ▼                │
               │       ┌───────────────┐         │
               │       │ AutomationCore│         │
               │       └───────┬───────┘         │
               │               │                 │
               │       ┌───────▼────────┐        │
               │       │ Device Manager │        │
               │       └───────┬────────┘        │
               │               │                 │
               │       ┌───────▼────────┐        │
               │       │ ADB /          │        │
               │       │ UIAutomator2   │        │
               │       └───────┬────────┘        │
               │               │                 │
               │       ┌───────▼────────┐        │
               │       │   BlueStacks   │        │
               │       │ Android Device │        │
               │       └────────────────┘        │
               └─────────────────────────────────┘
```

The critical architectural rule is: **REST and MCP are interfaces, not separate automation implementations.** Every operation flows through the same `AutomationCore`, which makes behavior, security, locking, logging, and testing consistent.
