from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.clinical.rules import interpret_labs  # noqa: E402
from app.agent.graph import run_agent  # noqa: E402


def test_hba1c_risk_range_is_available_with_empty_kb():
    result = interpret_labs({"hba1c_pct": 6.2})
    assert result["status"] == "OK"
    assert "hba1c_in_increased_risk_range_reference" in result["findings"]
    assert result["citations"] == []
    assert result["evidence_status"] == "reference_only"
    assert any(row["source_code"] == "KB-06" for row in result["reference_only"])


def test_fasting_seven_mmol_is_normalized_and_interpreted_at_diagnostic_threshold():
    result = interpret_labs({
        "glucose_value": 7, "glucose_unit": "mmol/L", "measurement_type": "fasting",
        "fasting_confirmed": True,
    })
    assert result["status"] == "OK"
    assert result["normalized_value_mg_dl"] == 126.13
    assert "fasting_glucose_at_or_above_diabetes_diagnostic_threshold" in result["findings"]
    assert result["diagnosis"] is False
    assert "Đây không phải chẩn đoán" in result["message"]
    assert result["rule_source"][0]["source_code"] == "KB-06"
    assert result["rule_source"][1]["source_code"] == "KB-01"
    assert result["rule_source"][1]["page"] == 11


def test_missing_glucose_unit_requests_clarification():
    result = interpret_labs({"glucose_value": 7, "measurement_type": "fasting"})
    assert result["status"] == "NEED_CLARIFICATION"
    assert result["result"] == "unit_required"


def test_hba1c_mmol_per_mol_is_explicitly_unsupported():
    result = interpret_labs({"hba1c_unit": "mmol/mol", "hba1c_pct": None})
    assert result["status"] == "UNSUPPORTED_UNIT"


def test_random_glucose_alone_does_not_make_a_diagnostic_conclusion():
    result = interpret_labs({
        "glucose_value": 220, "glucose_unit": "mg/dL", "measurement_type": "random",
    })
    assert result["status"] == "OK"
    assert "random_glucose_high_confirmation_required" in result["findings"]
    assert result["diagnosis"] is False
    assert result["confirmation_required"] is True


def test_agent_exposes_reference_only_rules_when_kb_is_empty():
    result = run_agent("HbA1c 6.2%", None, None)
    assert result["status"] == "OK"
    assert result["citations"] == []
    assert any(item["source_code"] == "KB-06" for item in result["reference_only"])
