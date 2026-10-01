"""Train the fare estimator and report what it is actually worth.

Run with:  python -m ml.train

Two things this script does that a quick training loop would not:

1. It reports honest, out-of-fold error via 5-fold cross-validation instead of
   quoting accuracy on the rows it memorised.
2. It fits a plain ridge regression on the same numeric features and prints it
   alongside. If the neural network does not beat a five-parameter linear
   model, that is worth knowing before it is put in front of commuters -- and
   with a dataset this small, it might not.

The model shipped for serving is then refit on all available rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from ml.data import load_publishable_fares, load_tariff, validate
from ml.features import StopVocab, encode_record
from ml.model import build_model, model_summary_lines

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACTS / "fare_model.keras"
VOCAB_PATH = ARTIFACTS / "vocab.json"
METRICS_PATH = ARTIFACTS / "metrics.json"

SEED = 42
FOLDS = 5
EPOCHS = 400
PATIENCE = 30
VALIDATION_SPLIT = 0.15


def set_seeds() -> None:
    import tensorflow as tf

    np.random.seed(SEED)
    tf.keras.utils.set_random_seed(SEED)
    try:
        tf.config.experimental.enable_op_determinism()
    except (AttributeError, RuntimeError):
        # Determinism is a nicety, not a requirement; older TF builds and some
        # GPUs legitimately refuse. Carry on.
        pass


def build_dataset(records: list[dict], vocab: StopVocab):
    from_ids, to_ids, numeric, fares = [], [], [], []
    for record in records:
        from_id, to_id, vector = encode_record(record, vocab)
        from_ids.append([from_id])
        to_ids.append([to_id])
        numeric.append(vector)
        fares.append(float(record["fareINR"]))
    return (
        np.array(from_ids, dtype="int32"),
        np.array(to_ids, dtype="int32"),
        np.array(numeric, dtype="float32"),
        np.array(fares, dtype="float32"),
    )


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Error in rupees, which is the only unit that means anything here."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    error = y_pred - y_true

    mae = float(np.mean(np.abs(error)))
    median_ae = float(np.median(np.abs(error)))
    within_20 = float(np.mean(np.abs(error) <= 20) * 100)
    within_40 = float(np.mean(np.abs(error) <= 40) * 100)

    spread = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float("nan") if spread == 0 else 1 - float(np.sum(error**2)) / spread

    return {
        "mae_inr": round(mae, 2),
        "median_abs_error_inr": round(median_ae, 2),
        "within_20_inr_pct": round(within_20, 1),
        "within_40_inr_pct": round(within_40, 1),
        "r2": round(r2, 4),
    }


def fit_ridge(x: np.ndarray, y: np.ndarray, lam: float = 1.0):
    """Closed-form ridge on the numeric features only (no stop embeddings).

    This is the honest baseline: same inputs minus the thing the network adds.
    """
    x_mean = x.mean(axis=0)
    y_mean = float(y.mean())
    x_centred = x - x_mean
    y_centred = y - y_mean
    gram = x_centred.T @ x_centred + lam * np.eye(x.shape[1])
    weights = np.linalg.solve(gram, x_centred.T @ y_centred)

    def predict(x_new: np.ndarray) -> np.ndarray:
        return (x_new - x_mean) @ weights + y_mean

    return predict


def cross_validate(from_ids, to_ids, numeric, fares, vocab_size: int) -> dict:
    """Pooled out-of-fold scores for the network, the ridge, and the mean."""
    import tensorflow as tf
    from tensorflow import keras

    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(fares))
    folds = np.array_split(order, FOLDS)

    oof_network = np.zeros_like(fares)
    oof_ridge = np.zeros_like(fares)
    best_epochs: list[int] = []

    for fold_index, test_idx in enumerate(folds, start=1):
        train_idx = np.setdiff1d(order, test_idx)

        model = build_model(vocab_size, seed=SEED + fold_index)
        history = model.fit(
            [from_ids[train_idx], to_ids[train_idx], numeric[train_idx]],
            fares[train_idx],
            epochs=EPOCHS,
            validation_split=VALIDATION_SPLIT,
            shuffle=False,
            callbacks=[keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=PATIENCE, restore_best_weights=True
            )],
            verbose=0,
        )
        best_epochs.append(int(np.argmin(history.history["val_loss"]) + 1))

        oof_network[test_idx] = model.predict(
            [from_ids[test_idx], to_ids[test_idx], numeric[test_idx]], verbose=0
        ).ravel()

        ridge = fit_ridge(numeric[train_idx], fares[train_idx])
        oof_ridge[test_idx] = ridge(numeric[test_idx])

        fold_mae = np.mean(np.abs(oof_network[test_idx] - fares[test_idx]))
        print(f"  fold {fold_index}/{FOLDS}: {len(train_idx)} train / "
              f"{len(test_idx)} test, network MAE Rs{fold_mae:.2f}")

    mean_baseline = np.full_like(fares, float(fares.mean()))
    return {
        "network": metrics(fares, oof_network),
        "ridge_baseline": metrics(fares, oof_ridge),
        "mean_baseline": metrics(fares, mean_baseline),
        "median_best_epoch": int(np.median(best_epochs)),
    }


def main() -> int:
    validate()
    set_seeds()

    records = load_publishable_fares()
    tariff = load_tariff()
    vocab = StopVocab.build(records)
    from_ids, to_ids, numeric, fares = build_dataset(records, vocab)

    print("=" * 68)
    print("RICKTRIX fare estimator")
    print("=" * 68)
    print(f"  training rows        {len(records)}")
    print(f"  distinct stops       {len(vocab.index)}")
    print(f"  fare range           Rs{fares.min():.0f} - Rs{fares.max():.0f} "
          f"(median Rs{np.median(fares):.0f})")
    print()

    print(f"cross-validating ({FOLDS}-fold, out-of-fold)...")
    scores = cross_validate(from_ids, to_ids, numeric, fares, vocab.size)
    print()

    print("  out-of-fold performance")
    for name, label in (
        ("network", "neural network"),
        ("ridge_baseline", "ridge baseline  "),
        ("mean_baseline", "predict-the-mean"),
    ):
        score = scores[name]
        print(f"    {label}  MAE Rs{score['mae_inr']:>6.2f}   "
              f"median Rs{score['median_abs_error_inr']:>5.2f}   "
              f"within Rs20 {score['within_20_inr_pct']:>5.1f}%   "
              f"R2 {score['r2']:>7.3f}")
    print()

    beats_ridge = scores["network"]["mae_inr"] < scores["ridge_baseline"]["mae_inr"]
    if beats_ridge:
        print("  -> the network does beat the linear baseline on the same features.")
    else:
        print("  -> WARNING: the network does NOT beat the ridge baseline. The extra")
        print("     capacity buys nothing on a dataset this small. Treat predictions")
        print("     as indicative only, and prefer mapped routes over estimates.")
    print()

    print(f"refitting on all {len(records)} rows...")
    model = build_model(vocab.size, seed=SEED)
    model.fit(
        [from_ids, to_ids, numeric],
        fares,
        epochs=max(50, scores["median_best_epoch"]),
        shuffle=False,
        verbose=0,
    )
    for line in model_summary_lines(model):
        print(f"  {line}")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    vocab.save(VOCAB_PATH)

    METRICS_PATH.write_text(json.dumps({
        "seed": SEED,
        "folds": FOLDS,
        "training_rows": len(records),
        "distinct_stops": len(vocab.index),
        "fare_range_inr": [float(fares.min()), float(fares.max())],
        "cross_validation": scores,
        "beats_ridge_baseline": beats_ridge,
        "tariff_reference": {
            "effective_from": tariff.get("effective_from"),
            "minimum_fare_inr": tariff.get("minimum_fare_inr"),
            "per_km_inr": tariff.get("per_km_inr"),
        },
        "caveats": [
            "autofare.js states its fares are user-provided and unverified "
            "against any central source; the model learns that unverified data.",
            "The dataset has no coordinates, distances or timestamps, so the "
            "model cannot reason about journey length - only about how well "
            "connected the endpoints are.",
            f"n={len(records)} is far too small for a reliable fare oracle. "
            "Estimates are a fallback for unmapped pairs, not a price list.",
            "Cross-validated error above is the honest estimate; the deployed "
            "model was refit on all rows and will look better in-sample.",
        ],
    }, indent=2), encoding="utf-8")

    print()
    print(f"saved model    {MODEL_PATH}")
    print(f"saved vocab    {VOCAB_PATH}")
    print(f"saved metrics  {METRICS_PATH}")
    print()
    print("Next:  python -m uvicorn app.main:app --reload --port 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
