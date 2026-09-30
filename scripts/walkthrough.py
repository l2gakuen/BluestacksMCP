#!/usr/bin/env python3
"""Walk the known Grindr screens, save each UI dump to a file, print one line per screen.

    export BS_TOKEN=...            # host .env AUTOMATION_API_TOKEN (never commit)
    python3 scripts/walkthrough.py [--all] [--show] [--out /tmp/bs-walk]

Screens: home, inbox, albums (+ interest, subscription with --all). Files: <out>/<screen>.json holds the normalized
elements; <out>/summary.json holds the compact view (texts only, in reading order). --show prints that compact view.
Stdlib only. Ends back on the home tab. Read-only: it only navigates tabs, never types or sends.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HOST = os.environ.get("BS_HOST", "10.147.17.183")
DEV = os.environ.get("BS_DEVICE", "bluestacks-1")
TOKEN = os.environ.get("BS_TOKEN") or sys.exit("export BS_TOKEN first")
BASE = f"http://{HOST}:8000/api/v1/devices/{DEV}"


def call(path, body=None, timeout=60):
    req = urllib.request.Request(f"{BASE}/{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)
    except Exception as e:  # network timeout etc.
        return {"error": {"code": "CLIENT", "message": str(e)}}


def retry(fn, tries=4, pause=3):
    for i in range(tries):
        r = fn()
        if "error" not in r:
            return r
        time.sleep(pause)
    return r


def click(sel):
    return retry(lambda: call("actions/click", {"selector": sel}))


def dump():
    return retry(lambda: call("ui?timeout_ms=30000", timeout=60))


SCREENS = [  # (name, steps to reach it, default?)
    ("home", [{"content_desc": "Onglet Accueil"}], True),
    ("inbox", [{"content_desc": "Onglet Boîte de réception"}, {"text": "Boîte de réception"}], True),
    ("albums", [{"text": "Albums"}], True),
    ("interest", [{"content_desc": "Interest Tab"}], False),
    ("subscription", [{"content_desc": "Onglet Abonnement"}], False),
]


def compact(elements):
    """Visible texts/descs in reading order, chrome included, as [text, x, y]."""
    out = [[e["text"] or e["content_desc"], e["bounds"][0], e["bounds"][1]]
           for e in elements if e["visible"] and (e["text"] or e["content_desc"])]
    return sorted(out, key=lambda t: (t[2] // 40, t[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also interest + subscription tabs")
    ap.add_argument("--show", action="store_true", help="print the compact texts of each screen")
    ap.add_argument("--out", default="/tmp/bs-walk")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    summary = {}
    for name, steps, default in SCREENS:
        if not (default or a.all):
            continue
        fail = next((r for s in steps if "error" in (r := click(s))), None)
        if fail:
            print(f"{name}: navigation failed: {fail['error']['code']} {fail['error']['message'][:80]}")
            continue
        time.sleep(2.5)
        d = dump()
        if "error" in d:
            print(f"{name}: dump failed: {d['error']['code']}")
            continue
        json.dump(d, open(f"{a.out}/{name}.json", "w"), ensure_ascii=False)
        summary[name] = compact(d["elements"])
        print(f"{name}: {len(d['elements'])} elements, {len(summary[name])} texts -> {a.out}/{name}.json")
        if a.show:
            print("  " + " | ".join(t[0][:24] for t in summary[name]))
    click({"content_desc": "Onglet Accueil"})  # leave on the home tab
    json.dump(summary, open(f"{a.out}/summary.json", "w"), ensure_ascii=False)
    print(f"summary -> {a.out}/summary.json")


if __name__ == "__main__":
    main()
