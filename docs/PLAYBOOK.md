# Operating the Android node: playbook for the next session

How to drive the BlueStacks node from another machine, what works, what bites, and the UI map of the
app that was explored (Grindr, `com.grindrapp.android`). Read this before touching the device.

## Connect

- Node: ZeroTier host `10.147.17.183`, REST `:8000`, MCP `:8001/mcp`, device id `bluestacks-1` (screen 900x1600, Android 9).
- Auth: `Authorization: Bearer <token>`. The token lives only in the host's `.env` (`AUTOMATION_API_TOKEN`); ask the
  user for it, **never write it into the repo, docs or memory**.
- Claude Code MCP: `claude mcp add --transport http android "http://10.147.17.183:8001/mcp" --header "Authorization: Bearer $TOKEN"`
  (restart the session so the `android_*` tools load). Without MCP, use REST via `source scripts/bs.sh`.
- Health: `GET /health` (no auth). `GET /api/v1/devices` shows `connected`.

## Tools (MCP name = REST route)

| Need | MCP tool | REST (under `/api/v1/devices/{id}`) |
|---|---|---|
| list / open / close apps | `android_list_apps`, `android_launch_app`, `android_stop_app`, `android_current_app` | `GET apps`, `POST actions/launch_app`, `POST actions/stop_app`, `GET app` |
| list UI elements | `android_dump_ui`, `android_find_element` | `GET ui`, `POST find` |
| parse on-screen data | `android_extract_text` (regex filter) | `POST extract` |
| click | `android_click_text`, `android_click_element` | `POST actions/click` (`{"text":..}` or `{"selector":{..}}`) |
| touch | `android_tap`, `android_long_press`, `android_swipe`, `android_scroll`, `android_pull_to_refresh` | `POST actions/{tap,long_press,swipe,scroll,pull_to_refresh}` |
| keyboard | `android_type`, `android_set_text`, `android_press` | `POST actions/{type,set_text,press}` |
| wait | `android_wait_for_text`, `android_wait_for_element` | `POST wait/{text,element}` |
| screenshot | `android_screenshot` | `GET screenshot` (PNG) |
| chain steps | (REST only) | `POST workflows` (max 50 steps, stops at first failure) |

### Selector (the important part)
`{"text","label","content_desc","resource_id","class_name","index","partial"}`, all given fields must match, exact by default.
- **`label`** matches `text` OR `content_desc`. Use it for icons/tabs: their name is usually a `content_desc`, so
  `click_text` on them fails with `ELEMENT_NOT_FOUND`.
- **`partial: true`** = case-insensitive substring (e.g. `{"label":"revenir en haut","partial":true}`).
- **`resource_id`** may omit the `pkg:id/` prefix (`quickbar_btn_chat`). Older builds required the full id.
- `index` picks among matches in document order. Only visible elements match.
- Prefer, in order: resource_id > content_desc/label > text > class_name > coordinates (last resort).

## Gotchas (learned on the real device)

0. **Keep the host awake**: a Windows/BlueStacks **screensaver or sleep makes screenshots and dumps hang or time out**
   (the requests then pile up behind the per-device lock and everything looks dead for a minute or two). Disable the
   screensaver/sleep on the host before long sessions.
0b. Screens with animation or a focused blinking text field, and the chat thread, can make `uiautomator dump` exceed the
   10 s action timeout. Retry with `GET ui?timeout_ms=30000` (or the MCP `timeout_ms`), else use a screenshot.

1. **UI dump is flaky** on busy/animated screens (video, transitions): `UI_AUTOMATION_ERROR` with empty `device_output`, or
   `TIMEOUT`. The core now retries 3x; still, wait ~2 s after navigation and retry the call. Screenshots keep working
   when the dump doesn't, use them to see the screen, and coordinates as the fallback.
2. **`set_text`/`type` "success" is not proof**: the dump may show the field empty right after. Verify with a screenshot.
3. **The app can change screen by itself** (profile pager advanced to another person mid-task). Re-dump/screenshot
   before any irreversible action (sending a message).
4. Tabs, icons, FABs: `content_desc`, not `text`. Grid tiles: only the username `TextView` carries text; tapping it opens the profile.
5. BACK from the inbox returns to the home grid.
6. The dump file is written to `/sdcard/window_dump.xml` on the device (harmless).
7. Never log or paste message contents; the node only logs `text_length`.
8. Sending messages / tapping the flame acts on real people through the user's account. Only do it when the user asked
   for that exact action; confirm the target first.

## UI map: Grindr (`com.grindrapp.android`)

Bottom tabs (`content_desc`): `Onglet Accueil`, `Interest Tab`, `Onglet Boîte de réception`, `Onglet Abonnement`.

**Home grid** (`.HomeActivityOriginal`): top bar `Votre profil`, `Emplacement actuel`, filter chips (text) `En ligne`,
`Âge`, `Position`, `Nouveaux`, `Étiquettes`; `Fab Boost`. Profile tiles = username `TextView`s (click by `text`).
After scrolling far down, a back-to-top control appears: `content_desc` **"Appuyer pour revenir en haut du fil"** (bounds ~[435,255,465,285]).
Recipe: `{"selector":{"label":"revenir en haut du fil","partial":true}}`, or `scroll up` repeatedly.

**Profile** (`.ui.profileV2.ProfilesActivity`), resource ids `com.grindrapp.android:id/...`:
`profile_display_name`, `profile_display_age`, `profile_last_seen_text`, `profile_near_text`, `profile_sexual_position`,
`profile_height_weight_tone`, `tag1..tagN`, toolbar buttons `menu_actions` ("Masquer le profil"), `menu_favorites`,
`Revenir en haut de la page` (ImageButton). Quick bar at the bottom:
`quickbar_input_click_overlay` (+ an `EditText`, placeholder "Dis quelque chose…", no id), `tap_main` (**the flame = "express interest", avoid**),
`quickbar_btn_chat` ("Discussion"). After typing, a yellow **send arrow** appears at the right of the field
(~(848,1551) on 900x1600); it had no dump entry (dump timed out), it was tapped by coordinates; the app then shows a
"Message envoyé !" toast and resets the field.

**Inbox** (tab `Onglet Boîte de réception`): sub-tabs (clickable `TextView`s, by text) `Boîte de réception` and `Albums`;
filter chips `non lu`, `Distance`, `En ligne`, `Position`. Each conversation row = clickable `View` (~[0,y,900,y+144],
step 146 px) + avatar `View` + `TextView`s: name, last-message preview, relative time (`41 min`, `3 h`), unread count.
Albums sub-tab: `MISES À JOUR`, `Mettre à jour votre album`, `TOUS LES ALBUMS`, `Créer un album`.
The chat thread is mapped below (from a screenshot: its UI dump kept timing out).

**Chat thread** (`.chat.presentation.ui.ChatActivityV2`, screen 900x1600; positions from a screenshot, not from a dump):
- Header: back arrow (~40,84), contact avatar with green "online" dot (~120,84), distance text ("à 3 km", ~183,98), overflow menu ⋮ (~852,84).
- Message list, newest at the bottom: a date separator ("Aujourd'hui", centered), **sent** bubbles yellow and right-aligned with the
  time under them, **received** bubbles blue and left-aligned with time + hint "Touchez deux fois pour aimer" (double tap = like).
  A system card "Accusés de lecture gratuits" (watch a video to unlock read receipts) can sit between messages.
- Input field "Dis quelque chose…" (~[24,1432,876,1516]) with a mic on the right; a send arrow replaces the mic once text is typed.
- Bottom action row (y~1558): camera (~113), emoji (~338), send location (~562), saved phrases/quotes (~788).
- Reading a thread: use `screenshot` (the dump is unreliable here) or `GET ui?timeout_ms=30000`.

## Recipes (REST `POST workflows`, or the same steps as separate tool calls)

Open inbox and read the conversation list:
```json
{"actions":[
  {"type":"click_element","selector":{"label":"Onglet Boîte de réception"}},
  {"type":"wait_element","selector":{"text":"Boîte de réception"},"timeout_ms":8000},
  {"type":"click_text","text":"Boîte de réception"}
]}
```
then `GET ui` (or `POST extract`) and read the row `TextView`s.

Back to the top of the grid: `{"type":"click_element","selector":{"label":"revenir en haut du fil","partial":true}}`.

Open a profile, write a short message, verify, then send (send only on the user's explicit request):
```json
{"actions":[
  {"type":"click_text","text":"<username on the grid>"},
  {"type":"wait_element","selector":{"resource_id":"quickbar_btn_chat"},"timeout_ms":8000},
  {"type":"set_text","selector":{"class_name":"android.widget.EditText"},"text":"<message>"}
]}
```
Then take a screenshot to confirm the text is in the field and the right person is on screen, then tap the send arrow
(look for a `content_desc` first; fall back to (848,1551)), then screenshot again for the "Message envoyé !" toast.

### Refresh profiles (profiles tab: go to top, then pull to refresh)
1. `click_element` `{"label":"Onglet Accueil"}` (on an old host: `{"content_desc":"Onglet Accueil"}`).
2. Go to the top: click `{"label":"revenir en haut du fil","partial":true}`; that control exists only after scrolling far
   down, so if it is `ELEMENT_NOT_FOUND` you are already near the top: `scroll up` a few times (`distance_pct` 80).
3. `POST actions/pull_to_refresh` (swipe from ~20% to ~60% of the screen height, 500 ms), wait ~5 s.
4. Compare the grid usernames before/after (`POST extract`, or `GET ui`). Both the default pull and a slow long swipe
   (`actions/swipe` 450,350 -> 450,1250, 1200 ms) executed fine and returned the same usernames: the gesture works,
   an unchanged grid just means the nearby profiles are the same (user confirmed). Don't treat it as a failure.

## Updating the host after code changes
See README, "Updating the Windows host": `git fetch --depth 1 origin main` and `git checkout origin/main -- src`, then restart.
