from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.safety.keyword_rules import normalize_vi

TRAINING_DATA_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "safety" / "safety_training_data.json"
CLASSIFIER_VERSION = "vi-char-tfidf-logistic-v2"


@lru_cache(maxsize=1)
def _classifier() -> Pipeline:
    data = json.loads(TRAINING_DATA_PATH.read_text(encoding="utf-8"))
    examples = data.get("examples", [])
    labels = {bool(row["emergency"]) for row in examples}
    if len(examples) < 8 or labels != {False, True}:
        raise ValueError("Safety classifier training examples are incomplete.")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char", ngram_range=(2, 5), min_df=1, max_features=20000,
            preprocessor=normalize_vi, lowercase=False,
        )),
        ("classifier", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ])
    pipeline.fit([row["text"] for row in examples], [int(row["emergency"]) for row in examples])
    return pipeline


def classify_emergency(message: str) -> dict[str, Any]:
    """Return a local, non-clinically-validated emergency signal."""
    model = _classifier()
    probabilities = model.predict_proba([message])[0]
    emergency_index = list(model.classes_).index(1)
    confidence = float(probabilities[emergency_index])
    return {
        "emergency": confidence >= 0.5,
        "confidence": round(confidence, 6),
        "classifier_version": CLASSIFIER_VERSION,
        "status": "ready_curated_not_clinically_validated",
    }
