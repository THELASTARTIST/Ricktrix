"""Request and response models for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RouteOut(BaseModel):
    """A route, shaped exactly like the object data.js builds in the browser."""

    id: int | None = None
    name: str
    from_: str = Field(alias="from")
    to: str
    fare: int | None = None
    via: list[str] = []
    area: str
    key: str

    model_config = {"populate_by_name": True}


class RoutePage(BaseModel):
    routes: list[RouteOut]
    total: int
    limit: int
    offset: int


class StopOut(BaseModel):
    name: str
    count: int | None = None


class StatsOut(BaseModel):
    """Real counts, so the UI can stop hardcoding "450+"."""

    routes: int
    stops: int
    areas: list[str]
    fare_min_inr: int | None = None
    fare_max_inr: int | None = None
    source: str


class FareRequest(BaseModel):
    from_: str = Field(alias="from", min_length=1, max_length=200)
    to: str = Field(alias="to", min_length=1, max_length=200)
    via_count: int = Field(default=0, ge=0, le=50)

    model_config = {"populate_by_name": True}


class FareResponse(BaseModel):
    """`source` is the important field.

    `observed` means this fare is a real mapped route and is authoritative.
    `estimated` means the model filled in for a pair we have not mapped, and
    should be shown with a hedge. Nothing else in the payload is worth more
    than that distinction.
    """

    from_: str = Field(alias="from")
    to: str = Field(alias="to")
    fare_inr: int
    source: str
    confidence: str
    model_info: dict | None = None
    tariff_floor_inr: float | None = None
    route: RouteOut | None = None
    caveat: str | None = None

    model_config = {"populate_by_name": True}


class SubmissionIn(BaseModel):
    from_name: str = Field(alias="from", min_length=2, max_length=200)
    to_name: str = Field(alias="to", min_length=2, max_length=200)
    fare_inr: int | None = Field(default=None, ge=1, le=10000)
    note: str | None = Field(default=None, max_length=1000)

    model_config = {"populate_by_name": True}

    @field_validator("from_name", "to_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("note")
    @classmethod
    def _clean_note(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class SubmissionOut(BaseModel):
    id: int
    status: str
    created_at: str | None = None
    message: str


class HealthOut(BaseModel):
    status: str
    model_ready: bool
    # "numpy" is the exported-weights path, "keras" the TensorFlow fallback.
    # If this ever says "keras" in production the container is carrying 600 MB
    # of TensorFlow it does not need.
    model_backend: str = "none"
    model_metrics: dict | None = None
    data_source: str
    supabase_configured: bool
    routes: int | None = None
    caveats: list[str] = []
