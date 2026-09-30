from __future__ import annotations

from src.core.errors import AutomationError
from src.models.actions import Selector

# Deterministic match: every provided field must match exactly; results keep document order,
# `index` picks among matches. Spec §26 priority (resource_id > content_desc > text > class+text)
# is honored by callers passing the strongest field; combined fields are ANDed.
FIELDS = ("resource_id", "content_desc", "text", "class_name")


def to_selector(sel: Selector | dict) -> Selector:
    if isinstance(sel, Selector):
        return sel
    try:
        return Selector(**sel)
    except Exception as e:  # pydantic ValidationError / TypeError
        raise AutomationError("INVALID_SELECTOR", str(e).splitlines()[0])


def matches(el: dict, sel: Selector) -> bool:
    return el["visible"] and all(getattr(sel, f) is None or el[f] == getattr(sel, f) for f in FIELDS)


def find_all(elements: list[dict], sel: Selector) -> list[dict]:
    return [e for e in elements if matches(e, sel)]


def find_one(elements: list[dict], sel: Selector) -> dict | None:
    hits = find_all(elements, sel)
    return hits[sel.index] if sel.index < len(hits) else None


def center(el: dict) -> tuple[int, int]:
    l, t, r, b = el["bounds"]
    return (l + r) // 2, (t + b) // 2
