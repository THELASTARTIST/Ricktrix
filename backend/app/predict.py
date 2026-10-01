"""Loading and calling the fare model.

The model is a fallback, not a source of truth. Callers should prefer a fare
that is already mapped in the database and only reach for this when a stop pair
is genuinely unknown -- and `predict()` refuses to return a number at all if
the model has not been trained, rather than inventing one.

Two backends, tried in order
----------------------------
`ml.export` lifts the trained weights into a .npz, and `_NumpyBackend`
evaluates them in a few matrix multiplies. That is the preferred path: it keeps
TensorFlow out of the server process entirely, which is what makes a small
container and a sub-second cold start possible. Keras is still supported as a
fallback so a server started without running the export keeps working.

Dropout is a no-op at inference in both backends, which is why the numpy
forward pass has no term for it.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

from ml.features import StopVocab, numeric_features


class ModelNotTrained(RuntimeError):
    """Raised when a prediction is requested before `python -m ml.train`."""


class _NumpyBackend:
    """The trained network evaluated directly from exported weights.

    Mirrors build_model() in ml/model.py: shared embedding, then three dense
    layers with relu on the first two.
    """

    def __init__(self, weights):
        self.embedding = weights["embedding"]
        self.w1, self.b1 = weights["w1"], weights["b1"]
        self.w2, self.b2 = weights["w2"], weights["b2"]
        self.w3, self.b3 = weights["w3"], weights["b3"]

    def __call__(self, from_id: int, to_id: int, vector: list[float]) -> float:
        x = np.concatenate(
            [
                self.embedding[from_id],
                self.embedding[to_id],
                np.asarray(vector, dtype=np.float32),
            ]
        )
        x = np.maximum(x @ self.w1 + self.b1, 0.0)
        x = np.maximum(x @ self.w2 + self.b2, 0.0)
        return float((x @ self.w3 + self.b3)[0])


class _KerasBackend:
    """The same network through Keras, for when the export has not been run."""

    def __init__(self, model):
        self.model = model

    def __call__(self, from_id: int, to_id: int, vector: list[float]) -> float:
        raw = self.model.predict(
            [
                np.array([[from_id]], dtype="int32"),
                np.array([[to_id]], dtype="int32"),
                np.array([vector], dtype="float32"),
            ],
            verbose=0,
        )
        return float(np.ravel(raw)[0])


class FarePredictor:
    """Thread-safe holder for the trained model and its vocabulary."""

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self.model_path = model_dir / "fare_model.keras"
        self.export_path = model_dir / "fare_model.npz"
        self.vocab_path = model_dir / "vocab.json"
        self.metrics_path = model_dir / "metrics.json"
        self._model = None
        self._vocab: StopVocab | None = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._model is not None and self._vocab is not None

    @property
    def backend(self) -> str:
        """Which backend is in use, for /api/health."""
        if isinstance(self._model, _NumpyBackend):
            return "numpy"
        if isinstance(self._model, _KerasBackend):
            return "keras"
        return "none"

    @property
    def vocab(self) -> StopVocab:
        if self._vocab is None:
            raise ModelNotTrained("vocabulary not loaded")
        return self._vocab

    def training_metrics(self) -> dict | None:
        """The cross-validated scores written by ml.train, for /api/health."""
        if not self.metrics_path.is_file():
            return None
        try:
            return json.loads(self.metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def load(self) -> bool:
        """Load the model if its artifacts exist. Returns whether it is ready."""
        with self._lock:
            if self.ready:
                return True
            if not self.vocab_path.is_file():
                return False
            try:
                self._vocab = StopVocab.load(self.vocab_path)
            except Exception:  # noqa: BLE001 - a broken artifact must not kill startup
                self._vocab = None
                return False

            if self.export_path.is_file():
                try:
                    with np.load(self.export_path) as weights:
                        self._model = _NumpyBackend({key: weights[key] for key in weights.files})
                    return True
                except Exception:  # noqa: BLE001
                    # Fall through to Keras rather than giving up.
                    self._model = None

            if self.model_path.is_file():
                try:
                    from tensorflow import keras

                    self._model = _KerasBackend(keras.models.load_model(str(self.model_path)))
                    return True
                except Exception:  # noqa: BLE001
                    self._model = None
            return False

    def predict(
        self, from_name: str, to_name: str, via_count: int = 0
    ) -> dict:
        """Estimate a fare in rupees for a stop pair.

        Returns a dict with the rounded fare plus the provenance the API needs
        to label the answer honestly, including whether either endpoint is a
        stop the model has actually seen.
        """
        if not self.ready:
            self.load()
        if not self.ready:
            raise ModelNotTrained(
                "fare model not found. Run `python -m ml.train` then "
                "`python -m ml.export` to build it."
            )

        from_id = self.vocab.encode(from_name)
        to_id = self.vocab.encode(to_name)
        vector = numeric_features(from_name, to_name, via_count, self.vocab)
        estimate = self._model(from_id, to_id, vector)

        return {
            "fare_inr": max(0, int(round(estimate))),
            "raw_fare_inr": round(estimate, 2),
            "known_stops": self.vocab.knows(from_name) and self.vocab.knows(to_name),
            "from_hub_routes": self.vocab.hubness_of(from_name),
            "to_hub_routes": self.vocab.hubness_of(to_name),
        }

    def predict_record(self, record: dict) -> dict:
        """Estimate for a dataset row, using its real `via` count."""
        return self.predict(
            record["from"], record["to"], via_count=len(record.get("via") or [])
        )
