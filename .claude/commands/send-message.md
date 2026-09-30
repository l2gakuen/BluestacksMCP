---
description: Send ONE message to ONE profile through the BlueStacks node (verified UI flow)
argument-hint: <profile name as on the grid> <exact message text>
---

Send exactly one message, to exactly one profile, with the user's exact text. `$ARGUMENTS` = profile name, then the text.
If either is missing or ambiguous, ask; do not guess a recipient or write the text yourself.

Rules
- One recipient, one message per invocation. No loops, no follow-ups, no auto-replies; the next message needs a new `/send-message`.
- Send the text verbatim. `input text` cannot type accents or emoji: if the text has them, tell the user and ask for an ASCII version before sending.
- Use UI elements (`text`, `content_desc`, `resource_id`), coordinates only when the dump fails (say so). Never swipe left/right on a profile.
- Check the screen with `android_current_app` (activity name) before each step; stop and report at the first surprise.
- Tools: the `android_*` MCP tools if loaded, else REST via `source scripts/bs.sh` (needs `BS_TOKEN`). Details: `docs/PLAYBOOK.md`.

Flow
1. `android_click_element` `{"content_desc":"Onglet Accueil"}` (home grid). `android_find_text` the profile name: it must match exactly one tile, otherwise stop and ask.
2. `android_click_text` the name. Wait ~4 s. Activity must contain `ProfilesActivity`; the dump's `profile_display_name` must equal the name.
3. Check `profile_last_chatted` / an existing thread: if the person already wrote, mention it to the user before replying.
4. `android_click_element` `{"resource_id":"com.grindrapp.android:id/quickbar_btn_chat"}`. Wait ~4 s. Activity must contain `ChatActivityV2`.
5. `android_click_element` the `android.widget.EditText`, then `android_type` the text. If the chat dump times out (`GET ui?timeout_ms=30000` first), fall back to `android_tap` (450,1474).
6. Click the send button from the dump; fallback `android_tap` (840,1476).
7. `android_press` BACK twice; activity must be `HomeActivityOriginal`.
8. Verify without screenshots: inbox tab (`content_desc` "Onglet Boîte de réception") then text "Boîte de réception", wait ~6 s, dump; the profile's row preview must show the text (or start with "Toi"). Return to "Onglet Accueil".
9. Report: recipient, text length, verified yes/no, coordinates used yes/no. Never repeat other people's messages beyond what the user asked.
