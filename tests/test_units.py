from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.clinical.rules import interpret_labs  # noqa: E402
from app.clinical.units import glucose_to_mg_dl  # noqa: E402


def test_glucose_conversion_and_measurement_context_are_explicit():
    assert round(glucose_to_mg_dl(7, "mmol/L"), 2) == 126.13
    missing_unit = interpret_labs({"glucose_value": 7, "measurement_type": "fasting"})
    assert missing_unit["status"] == "NEED_CLARIFICATION"
    missing_measurement = interpret_labs({"glucose_value": 126, "glucose_unit": "mg/dL"})
    assert missing_measurement["status"] == "NEED_CLARIFICATION"


def test_random_glucose_needs_clinical_context_before_any_diagnostic_conclusion():
    result = interpret_labs({"glucose_value": 220, "glucose_unit": "mg/dL", "measurement_type": "random"})
    assert result["status"] == "OK"
    assert result["diagnosis"] is False
    assert result["confirmation_required"] is True
