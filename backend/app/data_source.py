"""Where route data comes from.

Two implementations behind one interface:

* `LocalDataSource` reads autofare.js directly. Always available, zero setup --
  which means `run.bat` can start a working server before anyone has created a
  Supabase account.
* `SupabaseDataSource` queries the seeded database.

The Supabase source degrades to the local one per-request if a query fails, so
a bad migration or a dropped connection degrades the API rather than taking the
site down.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol

from app.areas import AREAS, route_area, route_key
from ml.data import load_publishable_fares, load_tariff

log = logging.getLogger(__name__)

MAX_LIMIT = 500


class Route(dict):
    """A route as the frontend expects it: the shape data.js produces, plus
    `area` and `key` so the client stops recomputing them."""


def _fare_of(record: dict) -> int | None:
    """The fare, whichever spelling it arrives under.

    autofare.js calls it `fareINR`, the database column is `fare_inr`, and the
    find_routes RPC returns `fare`. Accept all three so one shape serves every
    source.
    """
    for key in ("fare_inr", "fare", "fareINR"):
        value = record.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _shape(record: dict) -> Route:
    via = list(record.get("via") or [])
    from_name, to_name = record["from"], record["to"]
    return Route(
        id=record.get("id"),
        name=f"{from_name} ↔ {to_name}",
        **{"from": from_name},
        to=to_name,
        fare=_fare_of(record),
        via=via,
        area=record.get("area") or route_area(from_name, to_name, via),
        key=record_key(from_name, to_name),
    )


class DataSource(Protocol):
    name: str

    def list_routes(self, q=None, area=None, sort="default", limit=100, offset=0): ...
    def get_route(self, route_id): ...
    def match_route(self, from_name, to_name): ...
    def search_stops(self, q=None, limit=8): ...
    def popular_stops(self, limit=8): ...
    def stats(self) -> dict: ...
    def tariff(self) -> dict: ...


class LocalDataSource:
    """Serves autofare.js straight out of the repo. No database required."""

    name = "local"

    @lru_cache(maxsize=1)
    def _all(self) -> tuple[Route, ...]:
        return tuple(_shape(record) for record in load_publishable_fares())

    def _filtered(self, q, area, sort):
        routes = list(self._all())
        if q:
            needle = q.strip().lower()
            routes = [
                r
                for r in routes
                if needle in r["from"].lower()
                or needle in r["to"].lower()
                or any(needle in v.lower() for v in r["via"])
            ]
        if area and area != "All":
            routes = [r for r in routes if r["area"] == area]
        if sort == "fareAsc":
            routes.sort(key=lambda r: r["fare"])
        elif sort == "fareDesc":
            routes.sort(key=lambda r: r["fare"], reverse=True)
        elif sort == "az":
            routes.sort(key=lambda r: r["from"])
        return routes

    def list_routes(self, q=None, area=None, sort="default", limit=100, offset=0):
        routes = self._filtered(q, area, sort)
        return routes[offset: offset + limit], len(routes)

    def get_route(self, route_id):
        for route in self._all():
            if route["id"] == route_id:
                return route
        return None

    def match_route(self, from_name, to_name):
        target = route_key(from_name, to_name)
        for route in self._all():
            if route["key"] == target:
                return route
        return None

    def search_stops(self, q=None, limit=8):
        if not q:
            return []
        needle = q.strip().lower()
        counts = self._stop_counts()
        starts = [name for name in counts if name.lower().startswith(needle)]
        contains = [
            name for name in counts
            if needle in name.lower() and not name.lower().startswith(needle)
        ]
        ordered = sorted(starts) + sorted(contains)
        return [
            {"name": name, "count": counts[name]} for name in ordered[:limit]
        ]

    def popular_stops(self, limit=8):
        counts = self._stop_counts()
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"name": name, "count": count} for name, count in ranked[:limit]]

    @lru_cache(maxsize=1)
    def _stop_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for route in self._all():
            for name in (route["from"], route["to"], *route["via"]):
                counts[name] = counts.get(name, 0) + 1
        return counts

    def stats(self) -> dict:
        routes = self._all()
        fares = [r["fare"] for r in routes if isinstance(r["fare"], (int, float))]
        return {
            "routes": len(routes),
            "stops": len(self._stop_counts()),
            "areas": sorted({r["area"] for r in routes}),
            "fare_min_inr": min(fares) if fares else None,
            "fare_max_inr": max(fares) if fares else None,
            "source": self.name,
        }

    def tariff(self) -> dict:
        return load_tariff()


class SupabaseDataSource:
    """Queries the seeded database, falling back to autofare.js on any error."""

    name = "supabase"

    def __init__(self, client, fallback: LocalDataSource | None = None):
        self.client = client
        self.fallback = fallback or LocalDataSource()

    def _call(self, method: str, *args, **kwargs):
        try:
            return getattr(self.client, method)(*args, **kwargs).execute().data
        except Exception as exc:  # noqa: BLE001 - never let the DB take down the API
            log.warning("supabase %s failed (%s); serving autofare.js instead",
                        method, exc)
            return None

    def list_routes(self, q=None, area=None, sort="default", limit=100, offset=0):
        rows = self._call(
            "rpc",
            "find_routes",
            {
                "q_text": q,
                "q_area": area if area and area != "All" else None,
                "q_sort": sort,
                "q_limit": min(limit, MAX_LIMIT),
                "q_offset": offset,
            },
        )
        if rows is None:
            return self.fallback.list_routes(q, area, sort, limit, offset)
        return [_shape(row) for row in rows], len(rows)

    def get_route(self, route_id):
        rows = self._call("table", "routes").select("*").eq("id", route_id).limit(1)
        if not rows:
            return self.fallback.get_route(route_id)
        return _shape(rows[0])

    def match_route(self, from_name, to_name):
        rows = self._call("from", "routes").select("*").eq("key", route_key(from_name, to_name)).limit(1)
        if not rows:
            return self.fallback.match_route(from_name, to_name)
        return _shape(rows[0])

    def search_stops(self, q=None, limit=8):
        if not q:
            return []
        rows = self._call(
            "from", "stops"
        ).select("name").ilike("name", f"{q.strip()}%").limit(limit)
        if rows is None:
            return self.fallback.search_stops(q, limit)
        return [{"name": row["name"], "count": None} for row in rows]

    def popular_stops(self, limit=8):
        rows = self._call("rpc", "popular_stops", {"n": limit})
        if rows is None:
            return self.fallback.popular_stops(limit)
        return [{"name": row["name"], "count": row["count"]} for row in rows]

    def stats(self) -> dict:
        rows = self._call("rpc", "route_stats")
        if rows is None:
            return self.fallback.stats()
        return {**rows[0], "source": self.name}

    def tariff(self) -> dict:
        rows = self._call("from", "tariffs").select("*").order("effective_from", desc=True).limit(1)
        if not rows:
            return self.fallback.tariff()
        return rows[0]


@lru_cache(maxsize=1)
def get_data_source() -> DataSource:
    """Pick a source once, based on whether Supabase is configured."""
    from app import config

    if not config.using_supabase():
        log.info("SUPABASE_URL/SUPABASE_ANON_KEY not set - serving autofare.js")
        return LocalDataSource()

    try:
        from supabase import create_client

        client = create_client(config.supabase_url(), config.supabase_anon_key())
    except Exception as exc:  # noqa: BLE001
        log.warning("could not create Supabase client (%s) - serving autofare.js", exc)
        return LocalDataSource()

    log.info("using Supabase at %s", config.supabase_url())
    return SupabaseDataSource(client)


def known_areas() -> list[str]:
    return ["All", *AREAS]
