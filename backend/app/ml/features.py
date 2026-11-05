"""Public no-labs feature contract for the research-only model."""

from __future__ import annotations

FEATURES = ("age", "gender", "bmi", "hypertension", "heart_disease", "smoking_history")
MODEL_VERSION = "risk-no-labs-v1"


def missing_features(features: dict) -> list[str]:
    return [name for name in FEATURES if name not in features]
