from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database.session import SYNTHETIC_DATA_PATH, _synthetic_bundle, synthetic_data_fingerprint  # noqa: E402


def test_demo_profiles_are_file_seeded_and_within_observed_dataset_bounds():
    data = json.loads(SYNTHETIC_DATA_PATH.read_text(encoding="utf-8"))
    profiles, readings, _ = _synthetic_bundle()
    assert data["version"] == "demo-v1"
    assert "no Kaggle rows" in data["source"]
    assert all(row["data_origin"] == "synthetic" for row in profiles)
    assert {row["gender"] for row in profiles} == {"Male", "Female", "Other"}
    assert {row["smoking_history"] for row in profiles} == {
        "No Info", "never", "former", "current", "not current", "ever",
    }
    assert all(18 <= row["age"] <= 80 for row in profiles)
    assert all(10.01 <= row["bmi"] <= 91.82 for row in profiles)
    assert {row["original_unit"] for row in readings} == {"mg/dL", "mmol/L"}
    assert all(row["measurement_type"] in {"fasting", "random", "ogtt_2h"} for row in readings)
    assert all(row["source_type"] == "synthetic" for row in readings)


def test_demo_fingerprint_is_reproducible_from_exported_file():
    data = json.loads(SYNTHETIC_DATA_PATH.read_text(encoding="utf-8"))
    first = synthetic_data_fingerprint()
    assert first == synthetic_data_fingerprint()
    if data.get("fingerprint_sha256"):
        assert first == data["fingerprint_sha256"]
