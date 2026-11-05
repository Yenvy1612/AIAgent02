from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import _route_message, run_agent  # noqa: E402
from app.clinical.screening import screen_risk  # noqa: E402


def _complete_profile(age: int = 21, bmi: float = 22.9) -> str:
    return (
        f"Tôi có nguy cơ không? Tôi {age} tuổi, là nữ, chưa từng bị đái tháo đường thai kỳ; "
        "cha mẹ, anh chị em ruột và con đẻ không bị đái tháo đường; "
        "chưa được chẩn đoán tăng huyết áp; thường xuyên vận động; "
        f"BMI {bmi}."
    )


@pytest.mark.parametrize(("age", "expected"), [
    (39, 0), (40, 1), (49, 1), (50, 2), (59, 2), (60, 3),
])
def test_age_score_boundaries(age, expected):
    result = screen_risk(_complete_profile(age=age))
    assert result["scores"]["age"] == expected


@pytest.mark.parametrize(("bmi", "expected"), [
    (22.9, 0), (23, 1), (24.9, 1), (25, 2), (29.9, 2), (30, 3),
])
def test_bmi_score_boundaries(bmi, expected):
    result = screen_risk(_complete_profile(bmi=bmi))
    assert result["scores"]["bmi"] == expected


@pytest.mark.parametrize(("hypertension", "expected"), [(False, 4), (True, 5)])
def test_five_point_high_risk_threshold(hypertension, expected):
    statement = "đã được chẩn đoán tăng huyết áp" if hypertension else "chưa được chẩn đoán tăng huyết áp"
    message = (
        "Tôi có nguy cơ không? Tôi 60 tuổi, là nam, "
        "chưa từng bị đái tháo đường thai kỳ, không có người thân bậc một mắc bệnh, "
        f"{statement}, thường xuyên vận động, BMI 22.9."
    )
    result = screen_risk(message)
    assert result["score_min"] == expected
    assert result["score_max"] == expected
    assert ("từ ngưỡng 5" in result["answer"]) is (expected == 5)


def test_negations_and_grandmother_follow_the_questionnaire_rules():
    message = (
        "21 tuổi, chưa từng chẩn đoán ĐTĐ thai kì\n"
        "có bà bị đái tháo đường\n"
        "Chưa được chẩn đoán tăng huyết áp\n"
        "Thường xuyên vận động\n"
        "người bình thường không thừa cân"
    )
    result = screen_risk(message)

    assert result["score_min"] == 0
    assert result["score_max"] == 1
    assert result["scores"]["gestational_diabetes"] == 0
    assert result["scores"]["family_history"] == 0
    assert result["scores"]["hypertension"] == 0
    assert result["scores"]["activity"] == 0
    assert result["scores"]["bmi"] == 0
    assert "0 điểm, hoặc 1 điểm nếu là nam" in result["answer"]
    assert "dưới ngưỡng 5" in result["answer"]
    assert "bà không được tính" in result["answer"]
    assert "không phải chẩn đoán" in result["answer"]


def test_grandmother_mention_does_not_mark_user_as_diagnosed():
    result = screen_risk(
        "Tôi 35 tuổi, BMI 22, thường xuyên vận động, chưa từng bị tăng huyết áp. "
        "Bà tôi bị tiểu đường."
    )

    assert result["status"] == "OK"
    assert result["score_min"] == 0
    assert result["score_max"] == 1
    assert "bà không được tính" in result["answer"]


def test_missing_information_returns_a_range_and_requests_only_ambiguous_inputs():
    ambiguous = screen_risk("Tôi có nguy cơ mắc đái tháo đường không?")
    assert ambiguous["score_min"] == 0
    assert ambiguous["score_max"] == 10
    assert ambiguous["status"] == "NEED_INFORMATION"
    assert ambiguous["missing_factors"]

    below_threshold = screen_risk(
        "Tôi có nguy cơ không? 21 tuổi, nữ, chưa từng bị ĐTĐ thai kỳ, "
        "chưa tăng huyết áp, thường xuyên vận động, không thừa cân."
    )
    assert below_threshold["score_min"] == 0
    assert below_threshold["score_max"] == 1
    assert below_threshold["status"] == "OK"
    assert "dưới ngưỡng 5" in below_threshold["answer"]
    assert "gửi thêm" not in below_threshold["answer"]

    above_threshold = screen_risk("Tôi có nguy cơ không? 60 tuổi, là nam, đã được chẩn đoán tăng huyết áp.")
    assert above_threshold["score_min"] == 5
    assert above_threshold["score_max"] >= 5
    assert above_threshold["status"] == "OK"
    assert "từ ngưỡng 5" in above_threshold["answer"]
    assert "gửi thêm" not in above_threshold["answer"]


@pytest.mark.parametrize(("message", "reason"), [
    ("Tôi đã được chẩn đoán đái tháo đường. Tôi có nguy cơ không?", "diabetes_diagnosed"),
    ("Tôi đang mang thai. Tôi có nguy cơ mắc tiểu đường không?", "pregnancy"),
    ("Tôi 17 tuổi, có nguy cơ mắc đái tháo đường không?", "under_18"),
])
def test_screening_does_not_score_ineligible_people(message, reason):
    result = screen_risk(message)
    assert result["status"] == "NOT_SCORED"
    assert reason in result["excluded_reasons"]
    assert result["score_min"] is None
    assert result["score_max"] is None


def test_router_activates_for_two_factors_but_not_general_education_questions():
    assert _route_message("Tôi 40 tuổi và là nam.")[1] == ["screen_risk"]
    assert "screen_risk" not in _route_message("Tôi 40 tuổi.")[1]
    assert "screen_risk" not in _route_message("Yếu tố nguy cơ của đái tháo đường là gì?")[1]


def test_screening_does_not_change_any_of_the_30_rag_gold_routes():
    gold = json.loads((ROOT / "evaluation" / "rag" / "gold_questions.json").read_text(encoding="utf-8"))
    assert len(gold["questions"]) == 30
    assert all("screen_risk" not in _route_message(row["question"])[1] for row in gold["questions"])


def test_screening_cites_the_approved_appendix_chunk_and_reports_if_it_is_missing():
    result = screen_risk("Tôi có nguy cơ không?")
    assert result["citations"][0]["chunk_id"] == "KB-32-c329ac9f-012-0009"
    assert result["evidence"][0]["chunk_id"] == "KB-32-c329ac9f-012-0009"

    with patch("app.clinical.screening.knowledge_base._approved_chunks", return_value=[]):
        missing = screen_risk("Tôi có nguy cơ không?")
    assert missing["status"] == "SOURCE_MISSING"
    assert missing["citations"] == []
    assert "KB-32-c329ac9f-012-0009" in missing["answer"]


def test_screening_result_bypasses_llm_composer(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with patch("app.agent.graph.compose_answer", side_effect=AssertionError("screening must not call LLM")) as compose:
        response = run_agent("Tôi 25 tuổi, là nữ, thường xuyên vận động; tôi có nguy cơ không?", None, None)

    compose.assert_not_called()
    assert response["status"] == "NEED_INFORMATION"
    assert response["citations"][0]["chunk_id"] == "KB-32-c329ac9f-012-0009"
