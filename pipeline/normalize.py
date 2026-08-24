"""Shared normalization used by the scraper and the matcher.

All matching keys are derived here so the two sides of the comparison can
never drift apart. No record-specific logic — only generic string rules.
"""
import html
import re

# One canonical (abbreviated) form per common street-suffix / direction word.
_STREET_CANON = {
    "street": "st", "avenue": "ave", "road": "rd", "drive": "dr",
    "lane": "ln", "boulevard": "blvd", "pike": "pk", "court": "ct",
    "place": "pl", "parkway": "pkwy", "highway": "hwy", "circle": "cir",
    "terrace": "ter", "trail": "trl", "square": "sq", "crossing": "xing",
    "north": "n", "south": "s", "east": "e", "west": "w",
    "northwest": "nw", "northeast": "ne", "southwest": "sw", "southeast": "se",
}

# Words that carry no identity in facility names.
_NAME_STOPWORDS = {"the", "of", "at", "and"}

# Vocabulary canonicalization for facility names (applied before tokenizing).
_NAME_CANON = [
    (re.compile(r"\brehabilitation\b"), "rehab"),
    (re.compile(r"\bhealth\s+care\b"), "healthcare"),
    (re.compile(r"\bcentre\b"), "center"),
]

_PO_BOX_RE = re.compile(r"^\s*p\.?\s*o\.?\s*box\b", re.IGNORECASE)


def _clean(s):
    """Decode entities, lowercase, replace '&', strip punctuation to spaces."""
    s = html.unescape(s or "")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_key(s):
    s = _clean(s)
    for pat, repl in _NAME_CANON:
        s = pat.sub(repl, s)
    tokens = [t for t in s.split() if t not in _NAME_STOPWORDS]
    return " ".join(tokens)


def address_key(s):
    s = _clean(s)
    tokens = [_STREET_CANON.get(t, t) for t in s.split()]
    return " ".join(tokens)


def city_key(s):
    return _clean(s)


def state_key(s):
    return _clean(s).upper()


def person_key(s):
    return _clean(s)


def phone_key(s):
    return re.sub(r"\D", "", s or "")


def is_po_box(street):
    return bool(_PO_BOX_RE.match(street or ""))


def has_usable_street(street):
    """A street usable for address matching: non-empty and not a PO Box."""
    return bool((street or "").strip()) and not is_po_box(street)


def name_tokens(s):
    return set(name_key(s).split())
