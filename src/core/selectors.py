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


def _eq(have: str, want: str, partial: bool) -> bool:
    return want.lower() in have.lower() if partial else have == want


def matches(el: dict, sel: Selector) -> bool:
    """resource_id may be given without its 'pkg:id/' prefix; `label` matches text or content_desc."""
    if not el["visible"]:
        return False
    for f in FIELDS:
        want = getattr(sel, f)
        if want is None:
            continue
        have = el[f]
        if f == "resource_id":
            if have != want and not have.endswith("/" + want):
                return False
        elif f == "class_name":
            if have != want:
                return False
        elif not _eq(have, want, sel.partial):
            return False
    if sel.label is not None and not (_eq(el["text"], sel.label, sel.partial)
                                      or _eq(el["content_desc"], sel.label, sel.partial)):
        return False
    return True


def find_all(elements: list[dict], sel: Selector) -> list[dict]:
    return [e for e in elements if matches(e, sel)]


def find_one(elements: list[dict], sel: Selector) -> dict | None:
    hits = find_all(elements, sel)
    return hits[sel.index] if sel.index < len(hits) else None


def center(el: dict) -> tuple[int, int]:
    l, t, r, b = el["bounds"]
    return (l + r) // 2, (t + b) // 2
