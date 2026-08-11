"""Dependency-free binary secondary-intent baseline using character n-gram centroids."""

import math
import re
from collections import Counter
from dataclasses import dataclass


def character_ngrams(text: str, minimum: int = 2, maximum: int = 4) -> Counter[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    return Counter(
        normalized[start : start + size]
        for size in range(minimum, maximum + 1)
        for start in range(max(0, len(normalized) - size + 1))
    )


def _unit(vector: Counter[str]) -> dict[str, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0:
        raise ValueError("feature vector cannot be empty")
    return {key: value / norm for key, value in vector.items()}


def _cosine(left: Counter[str], right: dict[str, float]) -> float:
    norm = math.sqrt(sum(value * value for value in left.values()))
    if norm == 0:
        return 0.0
    return sum((value / norm) * right.get(key, 0.0) for key, value in left.items())


@dataclass(frozen=True)
class BinaryPrediction:
    positive: bool
    positive_similarity: float
    negative_similarity: float
    margin: float


class CharNgramCentroidBinaryHead:
    """Fixed zero-margin decision; no dev threshold fitting."""

    def __init__(self, positive_centroid: dict[str, float], negative_centroid: dict[str, float]):
        self.positive_centroid = positive_centroid
        self.negative_centroid = negative_centroid

    @classmethod
    def fit(cls, examples: tuple[tuple[str, bool], ...]) -> "CharNgramCentroidBinaryHead":
        positive = Counter[str]()
        negative = Counter[str]()
        for text, label in examples:
            (positive if label else negative).update(character_ngrams(text))
        if not positive or not negative:
            raise ValueError("both positive and negative training examples are required")
        return cls(_unit(positive), _unit(negative))

    def predict(self, text: str) -> BinaryPrediction:
        features = character_ngrams(text)
        positive = _cosine(features, self.positive_centroid)
        negative = _cosine(features, self.negative_centroid)
        margin = positive - negative
        return BinaryPrediction(
            positive=margin > 0,
            positive_similarity=positive,
            negative_similarity=negative,
            margin=margin,
        )
