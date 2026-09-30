# TODO (spec.md phases)

- [x] M1 Scaffold: config, errors, models, auth primitives
- [x] M2 Phase 1: ADB adapter, device manager, screenshot/tap/swipe/type/press/apps
- [x] M3 Phase 2: UI dump, selectors, click/set_text/wait
- [x] M4 Phase 3: REST API (auth, request IDs, structured errors, health)
- [x] M5 Phase 4: MCP server (tool allowlist, bearer auth)
- [x] M6 Phase 5/6: logging, per-device locks, workflows, authz, README/firewall docs

Deviation: UI dump uses `adb shell uiautomator dump` (UIAutomator via ADB), no
uiautomator2 on-device server; adapter is swappable (see adapters/uiautomator.py).
