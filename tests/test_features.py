from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.features import FEATURES, missing_features  # noqa: E402
from app.ml.preprocessing import prediction_frame  # noqa: E402


def test_no_labs_contract_selects_only_the_six_approved_features():
    sample = {
        "age": 44, "gender": "Female", "bmi": 26.1, "hypertension": 0,
        "heart_disease": 0, "smoking_history": "never",
        "year": 2019, "location": "unknown", "race:Asian": 0,
        "clinical_notes": "must never reach model", "hbA1c_level": 6.6,
        "blood_glucose_level": 155,
    }
    frame = prediction_frame(sample)
    assert tuple(frame.columns) == FEATURES
    assert "clinical_notes" not in frame and "year" not in frame
    assert "hbA1c_level" not in frame and "blood_glucose_level" not in frame
    assert missing_features({"age": 44}) == list(FEATURES[1:])
