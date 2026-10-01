"""The Keras architecture for fare estimation.

Deliberately tiny. With ~137 training rows anything larger memorises, and the
per-route fare data in autofare.js is explicitly unverified -- we would be
fitting noise with extra capacity. A small embedding bag plus a numeric MLP
gets the useful part of the signal and nothing more.
"""

from __future__ import annotations

from ml.features import EMBED_DIM, NUM_FEATURES


def build_model(num_stops: int, seed: int = 42):
    """Build an uncompiled-then-compiled fare regressor.

    Two categorical inputs (the `from` and `to` stop) share one embedding
    table, so a stop learned as a destination informs the same stop learned as
    an origin. This is what lets the model say anything at all about a stop
    pair it has never seen mapped.
    """
    from tensorflow import keras
    from tensorflow.keras import layers, regularizers

    keras.utils.set_random_seed(seed)

    from_stop = layers.Input(shape=(1,), dtype="int32", name="from_id")
    to_stop = layers.Input(shape=(1,), dtype="int32", name="to_id")
    numeric = layers.Input(shape=(NUM_FEATURES,), dtype="float32", name="numeric")

    # One shared table, regularised hard: n=137 and a few hundred stops.
    embedding = layers.Embedding(
        num_stops,
        EMBED_DIM,
        embeddings_regularizer=regularizers.l2(1e-5),
        name="stop_embedding",
    )
    # Input is (batch, 1) so the embedding comes back 3-D; flatten it back to
    # (batch, EMBED_DIM) or the Concatenate below will not line up.
    from_vec = layers.Flatten()(embedding(from_stop))
    to_vec = layers.Flatten()(embedding(to_stop))

    x = layers.Concatenate(name="merge")([from_vec, to_vec, numeric])
    # Named so ml.export can lift the weights out by name. Anything serving
    # this model without TensorFlow -- see app.predict -- is otherwise at the
    # mercy of the auto-generated dense, dense_1, dense_2 ordering.
    x = layers.Dense(32, activation="relu", name="hidden_1")(x)
    x = layers.Dropout(0.3, name="dropout")(x)
    x = layers.Dense(16, activation="relu", name="hidden_2")(x)
    output = layers.Dense(1, name="fare_inr")(x)

    model = keras.Model(
        inputs=[from_stop, to_stop, numeric],
        outputs=output,
        name="ricktrix_fare_model",
    )
    # MAE, not MSE: the loss is then directly "off by N rupees", which is the
    # unit the product actually cares about, and it is far less sensitive to
    # the handful of expensive long-haul routes in the set.
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mae",
        metrics=["mae"],
    )
    return model


def model_summary_lines(model) -> list[str]:
    return [
        f"total params: {model.count_params():,}",
        f"inputs: from_id, to_id, numeric({NUM_FEATURES})",
        f"embedding dim: {EMBED_DIM}",
    ]
