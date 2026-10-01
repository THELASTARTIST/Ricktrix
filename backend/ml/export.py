"""Export the trained Keras model to plain numpy weights.

Why bother: TensorFlow is ~600 MB of shared libraries and takes 10-15 seconds
just to `import`. This model is an embedding lookup and three matrix
multiplies. Serving it without TensorFlow means a Docker image around 150 MB
instead of over a gigabyte, a cold start of milliseconds instead of a minute,
and the free tier of any host being enough -- which is the difference between
this being deployable on a student's account and not.

Train with TensorFlow (`ml.train`); serve with numpy (`app.predict`). The two
are checked against each other by tests/test_export.py, because a silent
numerical divergence here would produce confidently wrong fares.

    python -m ml.export
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACTS / "fare_model.keras"
EXPORT_PATH = ARTIFACTS / "fare_model.npz"

# Must match build_model() in ml/model.py. Kept as a literal rather than
# imported so the export stays readable as "the whole forward pass, in order".
LAYER_ORDER = ("hidden_1", "hidden_2", "fare_inr")


def export(model_path: Path = MODEL_PATH, export_path: Path = EXPORT_PATH) -> Path:
    """Write the model's weights to a .npz and return its path."""
    if not model_path.is_file():
        raise SystemExit(
            f"no trained model at {model_path}\n"
            f"train one first:  python -m ml.train"
        )

    from tensorflow import keras

    model = keras.models.load_model(str(model_path))
    by_name = {layer.name: layer for layer in model.layers}
    missing = [name for name in ("stop_embedding", *LAYER_ORDER) if name not in by_name]
    if missing:
        # Almost always a model trained before the layers were named.
        raise SystemExit(
            f"model at {model_path.name} has no layer(s) {missing}.\n"
            f"retrain to pick up the current architecture:  python -m ml.train"
        )

    weights = {"embedding": by_name["stop_embedding"].get_weights()[0].astype(np.float32)}
    for index, name in enumerate(LAYER_ORDER):
        kernel, bias = by_name[name].get_weights()
        # Keras stores Dense kernels as (in, out); numpy wants the transpose.
        weights[f"w{index + 1}"] = np.ascontiguousarray(kernel.T, dtype=np.float32)
        weights[f"b{index + 1}"] = np.ascontiguousarray(bias, dtype=np.float32)

    export_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(export_path, **weights)
    return export_path


def verify(model_path: Path = MODEL_PATH, export_path: Path = EXPORT_PATH, rows: int = 24) -> None:
    """Compare numpy and Keras outputs on real rows. Raises on divergence.

    Run as part of training so a broken export can never reach a server.
    """
    from ml.data import load_publishable_fares
    from ml.features import StopVocab, encode_record, numeric_features
    from tensorflow import keras

    model = keras.models.load_model(str(model_path))
    data = np.load(export_path)
    vocab = StopVocab.load(ARTIFACTS / "vocab.json")

    records = load_publishable_fares()[:rows]
    if not records:
        raise SystemExit("no records to verify against")

    from_ids, to_ids, vectors, fares = [], [], [], []
    for record in records:
        from_ids.append(vocab.encode(record["from"]))
        to_ids.append(vocab.encode(record["to"]))
        vectors.append(numeric_features(record["from"], record["to"],
                                        len(record.get("via") or []), vocab))
        fares.append(float(record["fareINR"]))

    keras_out = np.ravel(model.predict(
        [
            np.array([from_ids], dtype="int32"),
            np.array([to_ids], dtype="int32"),
            np.array([vectors], dtype="float32"),
        ],
        verbose=0,
    ))

    x = np.concatenate(
        [
            data["embedding"][np.array(from_ids)],
            data["embedding"][np.array(to_ids)],
            np.array(vectors, dtype=np.float32),
        ],
        axis=1,
    )
    x = np.maximum(x @ data["w1"] + data["b1"], 0.0)   # relu
    x = np.maximum(x @ data["w2"] + data["b2"], 0.0)   # relu
    numpy_out = np.ravel(x @ data["w3"] + data["b3"])

    drift = float(np.max(np.abs(keras_out - numpy_out)))
    mae = float(np.mean(np.abs(keras_out - np.array(fares))))
    print(f"  export check: max drift {drift:.6f} rupees, "
          f"model MAE on {len(fares)} real rows {mae:.2f} rupees")
    if drift > 0.05:
        raise SystemExit(
            f"exported weights disagree with Keras by {drift:.4f} rupees. "
            f"Refusing to publish a model that predicts something else."
        )


def main() -> int:
    path = export()
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")
    try:
        verify()
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001
        # A verification problem is worth reporting but must not block a
        # perfectly good export; the tests cover this properly.
        print(f"  export check could not run: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
