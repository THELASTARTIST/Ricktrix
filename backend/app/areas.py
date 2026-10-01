"""Area classification, ported from all_routes.html so the API and the UI agree.

The browser has its own copy of this logic (routeArea in all_routes.html) and
keeps it for offline mode. The regexes below are ported verbatim on purpose:
drifting from them would mean a route is filed under one area online and
another offline. The area is computed once at seed time and stored as a column,
so filtering and sorting happen in the database rather than in every browser.
"""

from __future__ import annotations

import re

AREAS = [
    "Howrah",
    "Central Kolkata",
    "Salt Lake / EM Bypass",
    "South Kolkata",
    "Behala",
    "North Kolkata",
]

# Order matters -- the first match wins, exactly as in the original JS.
_AREA_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"howrah|ramrajatala|salkia"), "Howrah"),
    (re.compile(r"salt ?lake|ultadanga|karunamoyee|kestopur|bypass"), "Salt Lake / EM Bypass"),
    (re.compile(r"behala|kidderpore|metiabruz"), "Behala"),
    (re.compile(r"garia|jadavpur|tollygunge|ballygunge|dhakuria|rashbehari"), "South Kolkata"),
    (re.compile(r"shyambazar|dumdum|belgachia|bagbazar"), "North Kolkata"),
]

DEFAULT_AREA = "Central Kolkata"


def route_area(from_name: str, to_name: str, via: list[str] | None = None) -> str:
    """Classify a route into one of AREAS by its stop names."""
    haystack = " ".join([from_name, to_name, *(via or [])]).lower()
    for pattern, area in _AREA_PATTERNS:
        if pattern.search(haystack):
            return area
    return DEFAULT_AREA


def route_key(from_name: str, to_name: str) -> str:
    """The bookmark key the frontend already uses in localStorage.

    index.html, all_routes.html and saved_routes.html all key saved routes on
    `from + "|" + to` rather than the numeric id, so anything syncing bookmarks
    has to produce this exact string or existing saves will be orphaned.
    """
    return f"{from_name}|{to_name}"
