"""Seed Supabase from autofare.js.

    python -m scripts.seed              # requires .env with the service key
    python -m scripts.seed --dry-run    # prints the plan, touches nothing

Idempotent: stops upsert on their name, routes on their id. Re-running after
editing autofare.js brings the database back in line.
"""

from __future__ import annotations

import re
import sys

from app.areas import route_area, route_key
from app.config import load_env, supabase_service_key, supabase_url
from ml.data import load_publishable_fares, load_stops, load_tariff, validate

BATCH = 200


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "stop"


def collect() -> dict:
    """Build the full set of rows to write, from the one source of truth."""
    fares = load_publishable_fares()
    tariff = load_tariff()

    # Every distinct name that appears anywhere: the 272 bus stops plus any
    # from/to/via value the bus dataset did not know about.
    names: dict[str, None] = {name: None for name in load_stops()}
    for record in fares:
        for name in (record["from"], record["to"], *record["via"]):
            names[name] = None

    stops = [{"name": name, "slug": slugify(name)} for name in sorted(names)]
    stop_id = {row["name"]: index + 1 for index, row in enumerate(stops, start=1)}

    routes, via_rows = [], []
    for record in fares:
        from_name, to_name = record["from"], record["to"]
        via = list(record.get("via") or [])
        routes.append({
            "id": record["id"],
            "from_stop_id": stop_id[from_name],
            "to_stop_id": stop_id[to_name],
            "fare_inr": int(record["fareINR"]),
            "fare_source": record.get("fareSource"),
            "flag": record.get("flag"),
            "area": route_area(from_name, to_name, via),
            "key": route_key(from_name, to_name),
            "status": "published",
        })
        for position, name in enumerate(via):
            via_rows.append({
                "route_id": record["id"],
                "stop_id": stop_id[name],
                "position": position,
            })

    tariff_row = {
        "effective_from": tariff["effective_from"],
        "minimum_fare_inr": tariff["minimum_fare_inr"],
        "per_km_inr": tariff["per_km_inr"],
        "night_surcharge_percent": tariff.get("night_surcharge_percent"),
        "night_hours": tariff.get("night_hours"),
        "source": tariff.get("note_source"),
        "note": tariff.get("caveat"),
    }
    return {"stops": stops, "routes": routes, "route_via": via_rows,
            "tariffs": [tariff_row]}


def batches(rows: list, size: int = BATCH):
    for start in range(0, len(rows), size):
        yield rows[start: start + size]


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    validate()
    plan = collect()

    print("=" * 60)
    print("RICKTRIX seed plan")
    print("=" * 60)
    for table, rows in plan.items():
        print(f"  {table:<10} {len(rows):>5} rows")
    print()

    areas = sorted({r["area"] for r in plan["routes"]})
    for area in areas:
        count = sum(1 for r in plan["routes"] if r["area"] == area)
        print(f"  {area:<22} {count:>4} routes")
    print()

    if dry_run:
        print("--dry-run: nothing was written.")
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env, then:")
        print("  python -m scripts.seed")
        return 0

    if not (supabase_url() and supabase_service_key()):
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env")
        return 1

    from supabase import create_client

    client = create_client(supabase_url(), supabase_service_key())

    # The identity column means explicit ids in the insert would be ignored or
    # rejected, so let Postgres assign them and read them back by name.
    for chunk in batches(plan["stops"]):
        client.table("stops").upsert(chunk, on_conflict="name").execute()
    print(f"  stops     {len(plan['stops'])} written")

    for chunk in batches(plan["routes"]):
        client.table("routes").upsert(chunk, on_conflict="id").execute()
    print(f"  routes    {len(plan['routes'])} written")

    client.table("route_via").delete().neq("route_id", 0).execute()
    for chunk in batches(plan["route_via"]):
        client.table("route_via").insert(chunk).execute()
    print(f"  route_via {len(plan['route_via'])} written")

    # Replace the tariff rather than appending, so re-seeding stays idempotent.
    client.table("tariffs").delete().neq("id", 0).execute()
    client.table("tariffs").insert(plan["tariffs"]).execute()
    print(f"  tariffs   {len(plan['tariffs'])} written")

    print()
    print("Seed complete. Set SUPABASE_URL and SUPABASE_ANON_KEY to serve from it.")
    return 0


if __name__ == "__main__":
    load_env()
    sys.exit(main(sys.argv[1:]))
