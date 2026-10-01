"""The RICKTRIX API.

Start with:  python -m uvicorn app.main:app --reload --port 8000

Read endpoints work with no configuration at all -- they serve autofare.js
straight from the repo, so the server is useful before a database exists.
Set SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env to switch to the seeded
database, and SUPABASE_SERVICE_ROLE_KEY to accept route submissions.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.data_source import get_data_source, known_areas
from app.db import get_optional_user, get_service_client, require_admin, require_user
from app.predict import FarePredictor, ModelNotTrained
from app.schemas import (
    FareRequest,
    FareResponse,
    HealthOut,
    RouteOut,
    RoutePage,
    StatsOut,
    StopOut,
    SubmissionIn,
    SubmissionOut,
)
from ml.data import DatasetError, validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("ricktrix")

predictor = FarePredictor(config.model_dir())

ESTIMATE_CAVEAT = (
    "No mapped route for this pair. The figure is an estimate from a model "
    "trained on the fare dataset, which holds no coordinates, distances or "
    "timestamps -- so it cannot reason about how far the trip is. Treat it as "
    "a starting point to confirm with the driver, not a quote."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate()
        log.info("autofare.js parsed OK")
    except DatasetError as exc:
        log.error("autofare.js problem: %s", exc)
    if predictor.load():
        log.info("fare model loaded")
    else:
        log.warning(
            "no trained model found - /api/predict/fare will return 503. "
            "Run: python -m ml.train"
        )
    yield


app = FastAPI(
    title="RICKTRIX API",
    version="1.0.0",
    summary="Route data, fare estimation, and submissions for Kolkata share-autos.",
    description=__doc__,
    lifespan=lifespan,
)

# Only added when there is something to allow. With CORS_ORIGINS unset -- the
# default, and the deployed setup -- the API and the site share an origin and
# the browser makes no cross-origin request, so the middleware is not needed.
# Installing it unconditionally with an empty allow-list would just add a
# header to every response.
_origins = config.cors_origins()
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# --------------------------------------------------------------------------
# health & meta
# --------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    source = get_data_source()
    try:
        stats = source.stats()
        route_count = stats.get("routes")
    except Exception:  # noqa: BLE001 - health must never fail
        route_count = None
    return HealthOut(
        status="ok",
        model_ready=predictor.ready,
        model_backend=predictor.backend,
        model_metrics=predictor.training_metrics(),
        data_source=source.name,
        supabase_configured=config.using_supabase(),
        routes=route_count,
        caveats=[
            "Fares in autofare.js are user-provided and unverified against any "
            "central source.",
            "The estimator has no distance or coordinate data, so it models how "
            "connected the endpoints are -- not journey length.",
        ],
    )


@app.get("/api/stats", response_model=StatsOut, tags=["meta"])
def stats() -> StatsOut:
    """Real counts.

    index.html, all_routes.html and about.html currently hardcode "450+ routes"
    and a donut chart of [450, 0, 0, 0] while the dataset actually holds 137
    records. Point the UI at this and the numbers can never drift again.
    """
    return StatsOut(**get_data_source().stats())


@app.get("/api/tariff", tags=["meta"])
def tariff() -> dict:
    """The official CNG auto tariff formula, for sanity-checking estimates."""
    return get_data_source().tariff()


@app.get("/api/areas", tags=["meta"])
def areas() -> dict:
    return {"areas": known_areas()}


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------

@app.get("/api/routes", response_model=RoutePage, tags=["routes"])
def list_routes(
    q: str | None = Query(default=None, description="substring of from/to/via"),
    area: str | None = Query(default=None, description="All, or one area name"),
    sort: str = Query(default="default", pattern="^(default|fareAsc|fareDesc|az)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RoutePage:
    routes, total = get_data_source().list_routes(
        q=q, area=area, sort=sort, limit=limit, offset=offset
    )
    return RoutePage(routes=routes, total=total, limit=limit, offset=offset)


@app.get("/api/routes/match", response_model=RouteOut, tags=["routes"])
def match_route(
    from_: str = Query(alias="from"),
    to: str = Query(alias="to"),
) -> RouteOut:
    """Look up a route by its two endpoint names.

    Declared before /api/routes/{route_id} on purpose: FastAPI matches in
    declaration order, so the int path parameter would otherwise swallow the
    literal "match" and return a 422.
    """
    route = get_data_source().match_route(from_, to)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such route")
    return RouteOut(**route)


@app.get("/api/routes/{route_id}", response_model=RouteOut, tags=["routes"])
def get_route(route_id: int) -> RouteOut:
    route = get_data_source().get_route(route_id)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such route")
    return RouteOut(**route)


# --------------------------------------------------------------------------
# stops
# --------------------------------------------------------------------------

@app.get("/api/stops", response_model=list[StopOut], tags=["stops"])
def search_stops(
    q: str | None = Query(default=None, description="prefix of the stop name"),
    limit: int = Query(default=8, ge=1, le=50),
) -> list[StopOut]:
    return [StopOut(**s) for s in get_data_source().search_stops(q=q, limit=limit)]


@app.get("/api/stops/popular", response_model=list[StopOut], tags=["stops"])
def popular_stops(limit: int = Query(default=8, ge=1, le=50)) -> list[StopOut]:
    return [StopOut(**s) for s in get_data_source().popular_stops(limit=limit)]


# --------------------------------------------------------------------------
# fare estimation
# --------------------------------------------------------------------------

@app.post("/api/predict/fare", response_model=FareResponse, tags=["prediction"])
def predict_fare(request: FareRequest) -> FareResponse:
    """Fare for a stop pair, preferring a mapped route over any estimate.

    Returns `source: "observed"` with the authoritative fare when the pair is
    already in the dataset, and `source: "estimated"` from TensorFlow when it
    is not. A 503 means no model has been trained yet.
    """
    source = get_data_source()
    tariff_row = source.tariff()
    floor = tariff_row.get("minimum_fare_inr")

    route = source.match_route(request.from_, request.to)
    if route is not None:
        return FareResponse(
            **{
                "from": request.from_,
                "to": request.to,
                "fare_inr": route["fare"],
                "source": "observed",
                "confidence": "high",
                "tariff_floor_inr": floor,
                "route": RouteOut(**route),
            }
        )

    try:
        prediction = predictor.predict(
            request.from_, request.to, via_count=request.via_count
        )
    except ModelNotTrained as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    fare = prediction["fare_inr"]
    caveat = ESTIMATE_CAVEAT
    # The government minimum is a floor for metered rides. If the model
    # predicts below it, raise it to the floor and say that is what happened
    # rather than silently showing a different number from the one computed.
    if floor and fare < floor:
        fare = int(floor)
        caveat += (
            f" The model predicted below the Rs{floor:.0f} official minimum, "
            "so the minimum was used instead."
        )

    return FareResponse(
        **{
            "from": request.from_,
            "to": request.to,
            "fare_inr": fare,
            "source": "estimated",
            "confidence": "low" if not prediction["known_stops"] else "medium",
            "model_info": prediction,
            "tariff_floor_inr": floor,
            "caveat": caveat,
        }
    )


# --------------------------------------------------------------------------
# bookmarks
# --------------------------------------------------------------------------

def _bookmark_client_or_503():
    client = get_service_client()
    if client is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "bookmark sync needs SUPABASE_SERVICE_ROLE_KEY in backend/.env",
        )
    return client


@app.get("/api/bookmarks", tags=["bookmarks"])
async def list_bookmarks(user: dict = Depends(require_user)) -> dict:
    """Routes this user has saved, in the same shape as /api/routes.

    The frontend currently keeps these in localStorage under `ricktrix-saved`,
    keyed on "from|to" rather than the numeric id. Callers should keep reading
    localStorage first and treat this as the sync-on-login path, so existing
    saves are not orphaned.
    """
    client = _bookmark_client_or_503()
    try:
        rows = (
            client.table("bookmarks")
            .select("route_id")
            .eq("user_id", user["id"])
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        log.error("bookmark read failed: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "could not read bookmarks"
        ) from exc

    source = get_data_source()
    routes = []
    for row in rows:
        route = source.get_route(row["route_id"])
        if route is not None:
            routes.append(RouteOut(**route))
    return {"routes": routes, "count": len(routes)}


@app.post("/api/bookmarks", status_code=201, tags=["bookmarks"])
async def add_bookmark(
    route_id: int = Query(..., description="the route's numeric id"),
    user: dict = Depends(require_user),
) -> dict:
    client = _bookmark_client_or_503()
    try:
        client.table("bookmarks").upsert(
            {"user_id": user["id"], "route_id": route_id}, on_conflict="user_id,route_id"
        ).execute()
    except Exception as exc:  # noqa: BLE001
        log.error("bookmark insert failed: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "could not save the route"
        ) from exc
    return {"route_id": route_id, "saved": True}


@app.delete("/api/bookmarks/{route_id}", tags=["bookmarks"])
async def remove_bookmark(route_id: int, user: dict = Depends(require_user)) -> dict:
    client = _bookmark_client_or_503()
    try:
        client.table("bookmarks").delete().eq("user_id", user["id"]).eq(
            "route_id", route_id
        ).execute()
    except Exception as exc:  # noqa: BLE001
        log.error("bookmark delete failed: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "could not remove the route"
        ) from exc
    return {"route_id": route_id, "saved": False}


# --------------------------------------------------------------------------
# submissions
# --------------------------------------------------------------------------

@app.post("/api/submissions", response_model=SubmissionOut, status_code=201,
         tags=["submissions"])
async def submit_route(
    submission: SubmissionIn,
    user: dict | None = Depends(get_optional_user),
) -> SubmissionOut:
    """Accept a community route submission into the moderation queue.

    index.html currently resets the submit form and shows a thank-you toast,
    throwing the data away. This is where it goes instead.

    Works with no database: submissions are logged and reported as accepted so
    local development works, but they are NOT persisted until the service key
    is configured. Callers should not be told a submission is safe.
    """
    client = get_service_client()
    payload = {
        "user_id": (user or {}).get("id"),
        "from_name": submission.from_name,
        "to_name": submission.to_name,
        "fare_inr": submission.fare_inr,
        "note": submission.note,
        "status": "pending",
    }

    if client is None:
        log.info(
            "submission (not persisted, no service key): %s -> %s @ %s",
            submission.from_name, submission.to_name, submission.fare_inr,
        )
        return SubmissionOut(
            id=0,
            status="pending",
            message="accepted for review, but not stored: this server has no "
                    "database configured",
        )

    try:
        rows = client.table("route_submissions").insert(payload).execute().data
    except Exception as exc:  # noqa: BLE001
        log.error("submission insert failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="could not store the submission; please try again",
        ) from exc

    created = rows[0] if rows else {}
    return SubmissionOut(
        id=created.get("id", 0),
        status=created.get("status", "pending"),
        created_at=created.get("created_at"),
        message="thanks - your route is queued for community review",
    )


@app.get("/api/submissions", response_model=list[SubmissionOut], tags=["submissions"])
async def list_submissions(
    status_filter: str = Query(default="pending", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    _: dict = Depends(require_admin),
) -> list[SubmissionOut]:
    """The moderation queue. Admin sessions only."""
    client = get_service_client()
    if client is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "no database configured"
        )
    rows = (
        client.table("route_submissions")
        .select("*")
        .eq("status", status_filter)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    return [
        SubmissionOut(
            id=row["id"],
            status=row["status"],
            created_at=row.get("created_at"),
            message=f"{row.get('from_name')} -> {row.get('to_name')} "
                    f"@ {row.get('fare_inr')}",
        )
        for row in rows
    ]


@app.get("/api/", include_in_schema=False)
def api_root() -> dict:
    return {
        "name": "RICKTRIX API",
        "docs": "/docs",
        "health": "/api/health",
        "note": "Fares are user-provided and unverified; see /api/tariff.",
    }


# --------------------------------------------------------------------------
# static site
# --------------------------------------------------------------------------
# Mounted last, so /api/* and /docs are matched before this catch-all.
#
# It serves backend/public, which is a copy of the repo's html/js/css made by
# `python -m scripts.build_site` -- never the repo root itself, which would
# publish backend/.env and its service-role key over HTTP.

_SITE_DIR = config.BACKEND_ROOT / "public"

if (_SITE_DIR / "index.html").is_file():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_SITE_DIR), html=True), name="site")
    log.info("serving the static site from %s", _SITE_DIR)
else:
    log.info(
        "no staged site at %s - run `python -m scripts.build_site`. "
        "The API is still available at /api and /docs.",
        _SITE_DIR,
    )
