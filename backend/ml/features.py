"""Feature engineering shared by training and serving.

Both `ml.train` and `app.predict` import this module, and it is the only place
features are derived. That is deliberate: a model is only trustworthy if the
vectors it was fitted on are identical to the ones it is asked to score at
runtime. Do not duplicate any of this logic elsewhere.

Why these features and not coordinates
--------------------------------------
The dataset has no lat/lng, no distance, and no timestamps -- see the honesty
note at the top of autofare.js. So the model cannot learn "how far is this trip".
What it *can* learn is how a route's fare relates to how well-connected its
endpoints are. A stop that appears in twenty routes is a major hub, and a route
between two major hubs tends to cost more than one between two obscure stops.
That signal generalises to stop pairs we have never mapped, which is the one
thing a fallback estimator can usefully do.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

# Index 0 is reserved for unseen stops (the UNK embedding).
UNK = 0
EMBED_DIM = 8

# Order matters -- the model is fitted against exactly this layout.
# 0 log1p(hubness of `from`)
# 1 log1p(hubness of `to`)
# 2 log1p(hubness of `from` * hubness of `to`)
# 3 log1p(number of `via` stops)
# 4 whether the two endpoints share a significant word (a loop, usually short)
NUM_FEATURES = 5
NUMERIC_FEATURE_NAMES = [
    "log1p_from_hubness",
    "log1p_to_hubness",
    "log1p_hubness_product",
    "log1p_via_count",
    "shares_significant_token",
]

# Place names in this dataset are full of generic road furniture, which
# overlaps constantly and so carries no signal about a fare.
_NOISE_WORDS = {
    "road", "street", "station", "crossing", "more", "ghat", "nagar", "gate",
    "block", "phase", "para", "lane", "bypass", "junction", "corner", "stop",
    "north", "south", "east", "west", "new", "near", "opp",
}
_WORD = re.compile(r"[a-z]+")


def tokens(name: str) -> set[str]:
    """Meaningful lowercase words in a stop name."""
    return {
        word
        for word in _WORD.findall(name.lower())
        if len(word) > 2 and word not in _NOISE_WORDS
    }


class StopVocab:
    """Maps stop names to embedding indices and records how connected each is."""

    def __init__(self, index: dict[str, int], hubness: dict[str, int]):
        self.index = index
        self.hubness = hubness

    @property
    def size(self) -> int:
        """Embedding rows, including the reserved UNK row."""
        return len(self.index) + 1

    @classmethod
    def build(cls, records: list[dict]) -> "StopVocab":
        hubness: dict[str, int] = {}
        for record in records:
            names = [record["from"], record["to"], *record["via"]]
            for name in names:
                hubness[name] = hubness.get(name, 0) + 1
        # Sorted so the vocabulary is deterministic across rebuilds.
        index = {name: i + 1 for i, name in enumerate(sorted(hubness))}
        return cls(index=index, hubness=hubness)

    def encode(self, name: str) -> int:
        """Embedding index for a stop, or UNK if we have never seen it."""
        return self.index.get(name, UNK)

    def knows(self, name: str) -> bool:
        return name in self.index

    def hubness_of(self, name: str) -> int:
        return self.hubness.get(name, 0)

    def to_dict(self) -> dict:
        return {"index": self.index, "hubness": self.hubness}

    @classmethod
    def from_dict(cls, payload: dict) -> "StopVocab":
        return cls(index=payload["index"], hubness=payload["hubness"])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "StopVocab":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def numeric_features(
    from_name: str,
    to_name: str,
    via_count: int,
    vocab: StopVocab,
) -> list[float]:
    """The 5 dense inputs, in NUMERIC_FEATURE_NAMES order."""
    from_hub = vocab.hubness_of(from_name)
    to_hub = vocab.hubness_of(to_name)
    shared = 1.0 if tokens(from_name) & tokens(to_name) else 0.0
    return [
        math.log1p(from_hub),
        math.log1p(to_hub),
        math.log1p(from_hub * to_hub),
        math.log1p(max(0, via_count)),
        shared,
    ]


def encode_record(record: dict, vocab: StopVocab) -> tuple[int, int, list[float]]:
    """(from_id, to_id, numeric) for a training row."""
    return (
        vocab.encode(record["from"]),
        vocab.encode(record["to"]),
        numeric_features(record["from"], record["to"], len(record["via"]), vocab),
    )


def describe() -> str:
    """Human-readable summary of the feature layout, for the API docs page."""
    lines = [f"embedding dim {EMBED_DIM}, {NUM_FEATURES} numeric features:"]
    lines += [f"  {i}. {name}" for i, name in enumerate(NUMERIC_FEATURE_NAMES)]
    return "\n".join(lines)
