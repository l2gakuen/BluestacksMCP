#!/usr/bin/env bash
# Helper for driving the BlueStacks node from a shell:  source scripts/bs.sh
#   export BS_TOKEN=<AUTOMATION_API_TOKEN from the host's .env>   (never commit it)
#   export BS_HOST=10.147.17.183  BS_DEVICE=bluestacks-1          (defaults shown)
# Then:  bs_post actions/click '{"selector":{"label":"Onglet Accueil"}}' ; bs_dump /tmp/ui.json && bs_show /tmp/ui.json
: "${BS_HOST:=10.147.17.183}" "${BS_DEVICE:=bluestacks-1}"
: "${BS_TOKEN:?export BS_TOKEN first}"
BS_URL="http://$BS_HOST:8000/api/v1/devices/$BS_DEVICE"

bs_get()  { curl -sS -m 40 -H "Authorization: Bearer $BS_TOKEN" "$BS_URL/$1"; echo; }
bs_post() { curl -sS -m 40 -H "Authorization: Bearer $BS_TOKEN" -H "Content-Type: application/json" -d "${2:-{\}}" "$BS_URL/$1"; echo; }
bs_shot() { curl -sS -m 40 -H "Authorization: Bearer $BS_TOKEN" -o "${1:-/tmp/bs.png}" "$BS_URL/screenshot" && echo "saved ${1:-/tmp/bs.png}"; }
# UI dump to a file, retried (older hosts without server-side retry flake on busy screens)
bs_dump() { for i in 1 2 3 4; do curl -sS -m 45 -H "Authorization: Bearer $BS_TOKEN" "$BS_URL/ui" -o "$1"; grep -q '"elements"' "$1" && return 0; sleep 3; done; return 1; }
# Compact listing of visible labelled/clickable elements: class | label | id | bounds | C(lickable)
bs_show() { python3 - "$1" <<'PY'
import json,sys
els=[e for e in json.load(open(sys.argv[1]))["elements"] if e["visible"]]
print(len(els),"elements")
for e in els:
    if e["text"] or e["content_desc"] or (e["clickable"] and e["resource_id"]):
        print(e["class_name"].split(".")[-1],"|",(e["text"] or e["content_desc"])[:50].replace("\n"," "),"|",
              e["resource_id"].split("/")[-1],"|",e["bounds"],"C" if e["clickable"] else "")
PY
}
# POST until success (transient dump failures): bs_retry actions/click '{"text":"Max"}'
bs_retry() { for i in 1 2 3 4; do r=$(bs_post "$1" "$2"); echo "$r" | grep -q '"success": *true' && { echo "$r"; return 0; }; sleep 3; done; echo "$r"; return 1; }
