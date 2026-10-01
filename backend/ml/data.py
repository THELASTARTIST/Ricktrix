"""Read the fare dataset straight out of autofare.js.

autofare.js is the single source of truth for the frontend, so we parse it
rather than keeping a second copy that can silently drift. The three literals
we need (autoFares, busRouteStops, officialTariff) are JSON-compatible once
unquoted keys are quoted and trailing commas are dropped.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

# backend/ml/data.py -> backend/ml -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOFARE_JS = REPO_ROOT / "autofare.js"

# A key at the start of an object or after a comma, e.g. `{ id:` or `, to:`.
_UNQUOTED_KEY = re.compile(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:")
# A comma immediately before a closing brace/bracket.
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

# data.js drops records with these endpoints before showing anything, so the
# seeded database must apply the same filter or the API and the UI disagree.
PLACEHOLDER = "Not Specified"


class DatasetError(RuntimeError):
    """Raised when autofare.js is missing or no longer parseable."""


def _js_to_json(text: str) -> str:
    """Normalise a JavaScript object/array literal into valid JSON."""
    text = _UNQUOTED_KEY.sub(r'\1"\2":', text)
    text = _TRAILING_COMMA.sub(r"\1", text)
    return text


def _extract_literal(source: str, name: str) -> str:
    """Return the balanced [...] or {...} literal that follows `const name = `."""
    marker = f"const {name} = "
    try:
        start = source.index(marker) + len(marker)
    except ValueError as exc:
        raise DatasetError(f"could not find `{name}` in autofare.js") from exc

    opener = source[start]
    closer = {"[": "]", "{": "}"}.get(opener)
    if closer is None:
        raise DatasetError(f"`{name}` is not an object or array literal")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise DatasetError(f"unterminated literal for `{name}`")


@lru_cache(maxsize=1)
def _source() -> str:
    if not AUTOFARE_JS.is_file():
        raise DatasetError(f"autofare.js not found at {AUTOFARE_JS}")
    return AUTOFARE_JS.read_text(encoding="utf-8")


def _load(name: str):
    try:
        return json.loads(_js_to_json(_extract_literal(_source(), name)))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"`{name}` in autofare.js is not parseable: {exc}") from exc


def load_fares() -> list[dict]:
    """All fare records, including the ones the UI hides."""
    return _load("autoFares")


def load_publishable_fares() -> list[dict]:
    """Fare records the frontend actually shows, matching data.js's filter."""
    return [
        record
        for record in load_fares()
        if record.get("from") != PLACEHOLDER and record.get("to") != PLACEHOLDER
    ]


def load_stops() -> list[str]:
    """The 272 unique bus stop names used to cross-reference route endpoints."""
    return _load("busRouteStops")


def load_tariff() -> dict:
    """The official CNG auto tariff formula, as published Feb 2025."""
    return _load("officialTariff")


def validate() -> None:
    """Fail loudly at startup if autofare.js no longer matches what we expect."""
    fares = load_publishable_fares()
    if not fares:
        raise DatasetError("no publishable fare records found in autofare.js")

    required = {"id", "from", "to", "via", "fareINR"}
    for record in fares:
        missing = required - record.keys()
        if missing:
            raise DatasetError(
                f"fare record {record.get('id', '?')} is missing {sorted(missing)}"
            )
        if not isinstance(record["via"], list):
            raise DatasetError(f"fare record {record['id']} has a non-list `via`")
        if not isinstance(record["fareINR"], (int, float)):
            raise DatasetError(f"fare record {record['id']} has a non-numeric fareINR")


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    validate()
    publishable = load_publishable_fares()
    print(f"autofare.js: {len(load_fares())} records, {len(publishable)} publishable")
    print(f"bus stops:   {len(load_stops())}")
    print(f"tariff:      min {load_tariff()['minimum_fare_inr']}, "
          f"per km {load_tariff()['per_km_inr']}")
