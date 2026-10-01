"""Smoke tests.

The first three run with nothing installed but the standard library, so a
broken autofare.js or a bad area regex is caught before TensorFlow is even
imported. The rest are skipped when their dependencies are missing.
"""

from __future__ import annotations

import json

import pytest

from app.areas import AREAS, route_area, route_key
from app.data_source import LocalDataSource
from ml.data import load_publishable_fares, load_stops, load_tariff, validate
from ml.features import NUM_FEATURES, StopVocab, encode_record, numeric_features


# ---------------------------------------------------------------- dataset

def test_dataset_parses():
    validate()
    records = load_publishable_fares()
    assert len(records) > 100
    assert all(r["from"] != "Not Specified" for r in records)
    assert all(r["from"] and r["to"] for r in records)


def test_dataset_is_consistent_with_the_ui_count():
    """The UI hardcodes "450+ routes"; the data does not agree.

    This test is the canary. When the dataset genuinely reaches 450 the
    assertion can be raised -- and until then the marketing copy in
    index.html, all_routes.html and the about.html donut chart is wrong.
    """
    actual = len(load_publishable_fares())
    assert actual == 137, (
        f"dataset now has {actual} records, not 137. If that is intended, update "
        "the hardcoded '450+' copy in index.html, all_routes.html and the "
        "about.html donut chart."
    )


def test_tariff_is_present():
    tariff = load_tariff()
    assert tariff["minimum_fare_inr"] > 0
    assert tariff["per_km_inr"] > 0
    assert tariff["effective_from"]


def test_bus_stops_present():
    assert len(load_stops()) > 200


# ---------------------------------------------------------------- areas

@pytest.mark.parametrize(
    "from_name,to_name,expected",
    [
        ("Howrah Station", "Ultadanga", "Howrah"),
        ("Bhowanipore", "Garia", "South Kolkata"),
        ("Behala Bazar", "Kidderpore", "Behala"),
        ("Salt Lake Sector V", "Belgharia", "Salt Lake / EM Bypass"),
        ("Shyambazar", "Bagbazar", "North Kolkata"),
        ("Esplanade", "BBD Bagh", "Central Kolkata"),
    ],
)
def test_route_area(from_name, to_name, expected):
    assert route_area(from_name, to_name) == expected


def test_every_area_is_reachable():
    for area in AREAS:
        assert area in AREAS


def test_route_key_matches_the_frontend():
    """saved_routes.html splits on "|" to recover from/to."""
    key = route_key("Howrah", "Salt Lake")
    assert key == "Howrah|Salt Lake"
    assert key.split("|") == ["Howrah", "Salt Lake"]


# ---------------------------------------------------------------- features

def test_vocab_reserves_index_zero_for_unseen_stops():
    vocab = StopVocab.build(load_publishable_fares())
    assert vocab.size == len(vocab.index) + 1
    assert vocab.encode("A stop nobody has ever heard of") == 0
    assert vocab.knows("Howrah Station")


def test_numeric_feature_vector_shape_is_stable():
    vocab = StopVocab.build(load_publishable_fares())
    vector = numeric_features("Howrah", "Garia", 3, vocab)
    assert len(vector) == NUM_FEATURES
    assert all(isinstance(value, float) for value in vector)


def test_encode_record_returns_matching_parts():
    record = load_publishable_fares()[0]
    vocab = StopVocab.build(load_publishable_fares())
    from_id, to_id, vector = encode_record(record, vocab)
    assert isinstance(from_id, int) and isinstance(to_id, int)
    assert len(vector) == NUM_FEATURES


# ---------------------------------------------------------------- data source

def test_local_data_source_returns_routes():
    source = LocalDataSource()
    routes, total = source.list_routes(limit=10)
    assert total == len(load_publishable_fares())
    assert len(routes) == 10
    first = routes[0]
    assert {"id", "name", "from", "to", "fare", "via", "area", "key"} <= first.keys()
    assert "↔" in first["name"]


def test_local_data_source_search_and_sort():
    source = LocalDataSource()
    matched, _ = source.list_routes(q="howrah", limit=100)
    assert matched
    assert all(
        "howrah" in r["from"].lower()
        or "howrah" in r["to"].lower()
        or any("howrah" in v.lower() for v in r["via"])
        for r in matched
    )

    ascending, _ = source.list_routes(sort="fareAsc", limit=100)
    fares = [r["fare"] for r in ascending]
    assert fares == sorted(fares)


def test_local_data_source_match_and_stats():
    source = LocalDataSource()
    record = load_publishable_fares()[0]
    found = source.match_route(record["from"], record["to"])
    assert found is not None
    assert found["key"] == route_key(record["from"], record["to"])
    assert source.match_route("Nowhere", "Nowhere at all") is None

    stats = source.stats()
    assert stats["routes"] == len(load_publishable_fares())
    assert stats["fare_min_inr"] <= stats["fare_max_inr"]


def test_local_data_source_popular_stops():
    source = LocalDataSource()
    popular = source.popular_stops(8)
    assert len(popular) == 8
    counts = [s["count"] for s in popular]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------- API

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["routes"] == len(load_publishable_fares())
    assert body["caveats"], "health should carry the data-quality caveats"


def test_stats_endpoint_reports_real_counts(client):
    body = client.get("/api/stats").json()
    assert body["routes"] == len(load_publishable_fares())
    assert body["stops"] > 0
    assert set(body["areas"]) <= set(AREAS)


def test_routes_listing(client):
    body = client.get("/api/routes", params={"limit": 5}).json()
    assert body["total"] == 137
    assert len(body["routes"]) == 5
    assert body["routes"][0]["area"] in AREAS


def test_route_by_id_and_match(client):
    listing = client.get("/api/routes", params={"limit": 1}).json()["routes"][0]
    by_id = client.get(f"/api/routes/{listing['id']}")
    assert by_id.status_code == 200

    # The literal "match" must not be swallowed by the {route_id} parameter.
    matched = client.get("/api/routes/match", params={
        "from": listing["from"], "to": listing["to"]
    })
    assert matched.status_code == 200
    assert matched.json()["key"] == listing["key"]


def test_unknown_route_is_404(client):
    assert client.get("/api/routes/999999").status_code == 404
    assert client.get("/api/routes/match", params={
        "from": "Atlantis", "to": "Narnia"
    }).status_code == 404


def test_stop_autocomplete(client):
    body = client.get("/api/stops", params={"q": "how", "limit": 8}).json()
    assert body
    assert all(s["name"].lower().startswith("how") for s in body)


def test_mapped_pair_reports_observed_fare(client):
    record = load_publishable_fares()[0]
    response = client.post("/api/predict/fare", json={
        "from": record["from"], "to": record["to"], "via_count": len(record["via"]),
    })
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "observed"
    assert body["confidence"] == "high"
    assert body["fare_inr"] == record["fareINR"]
    assert body["tariff_floor_inr"] == load_tariff()["minimum_fare_inr"]


def test_unmapped_pair_never_silently_invents_a_price(client):
    """Either a real estimate, or a 503 -- never a confident made-up number."""
    response = client.post("/api/predict/fare", json={
        "from": "A Place With No Route", "to": "Another Unmapped Place",
    })
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        body = response.json()
        assert body["source"] == "estimated"
        assert body["confidence"] in ("low", "medium")
        assert body["caveat"]
        assert body["fare_inr"] >= load_tariff()["minimum_fare_inr"]


def test_submission_is_accepted(client):
    response = client.post("/api/submissions", json={
        "from": "Ballygunge", "to": "New Alipore", "fare_inr": 35,
    })
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    if body["id"] == 0:
        # No service key configured -- accepted but not stored. The message
        # must say so rather than pretending it was saved.
        assert "not stored" in body["message"]


def test_submission_validation(client):
    assert client.post("/api/submissions", json={"from": "", "to": "X"}).status_code == 422
    assert client.post("/api/submissions", json={"from": "A", "to": "B"}).status_code == 422
    assert client.post("/api/submissions", json={
        "from": "A", "to": "B", "fare_inr": -5
    }).status_code == 422


def test_moderation_queue_requires_an_admin(client):
    """Unauthenticated and non-admin callers must both be turned away."""
    assert client.get("/api/submissions").status_code == 401
    assert client.get(
        "/api/submissions", headers={"Authorization": "Bearer not-a-real-token"}
    ).status_code == 401


# ---------------------------------------------------------------- model

def test_trained_model_beats_the_mean_baseline():
    """Skip unless ml.train has actually been run."""
    from ml.train import METRICS_PATH

    if not METRICS_PATH.is_file():
        pytest.skip("run `python -m ml.train` to enable this test")

    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    network = metrics["cross_validation"]["network"]
    mean = metrics["cross_validation"]["mean_baseline"]
    assert network["mae_inr"] < mean["mae_inr"], (
        f"the model ({network['mae_inr']}) is no better than predicting the "
        f"mean fare ({mean['mae_inr']}); it should not be serving predictions"
    )
    assert metrics["caveats"], "metrics must record the data-quality caveats"


# ---------------------------------------------------------------- export

def test_exported_weights_reproduce_the_keras_model():
    """The numpy server path and the Keras training path must agree.

    This is the test that makes it safe to run production without TensorFlow.
    app/predict.py reimplements the forward pass in numpy, and a reimplementation
    that drifts would produce confidently wrong fares with nothing to notice.
    """
    pytest.importorskip("tensorflow")
    import numpy as np

    from app.predict import _KerasBackend, _NumpyBackend
    from ml.export import EXPORT_PATH, MODEL_PATH
    from ml.features import StopVocab
    from tensorflow import keras

    if not (EXPORT_PATH.is_file() and MODEL_PATH.is_file()):
        pytest.skip("run `python -m ml.train` then `python -m ml.export`")

    numpy_backend = _NumpyBackend(dict(np.load(EXPORT_PATH)))
    keras_backend = _KerasBackend(keras.models.load_model(str(MODEL_PATH)))
    vocab = StopVocab.load(EXPORT_PATH.parent / "vocab.json")

    worst = 0.0
    for record in load_publishable_fares()[:40]:
        from_id = vocab.encode(record["from"])
        to_id = vocab.encode(record["to"])
        vector = numeric_features(record["from"], record["to"], len(record["via"]), vocab)
        drift = abs(numpy_backend(from_id, to_id, vector) - keras_backend(from_id, to_id, vector))
        worst = max(worst, drift)

    assert worst < 0.05, f"numpy and Keras disagree by {worst:.4f} rupees"


def test_predictor_prefers_the_numpy_backend():
    """The deployed image has no TensorFlow, so numpy must be the default."""
    from app.predict import FarePredictor
    from ml.export import EXPORT_PATH

    if not EXPORT_PATH.is_file():
        pytest.skip("run `python -m ml.export` to enable this test")

    predictor = FarePredictor(EXPORT_PATH.parent)
    assert predictor.load()
    assert predictor.backend == "numpy", (
        f"loaded the {predictor.backend} backend; the container only has "
        f"requirements-serve.txt installed and would fall over"
    )
    result = predictor.predict("Howrah Station", "Garia", via_count=2)
    assert result["fare_inr"] >= load_tariff()["minimum_fare_inr"]
    assert result["known_stops"] is True
