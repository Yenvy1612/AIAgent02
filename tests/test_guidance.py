from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import _route_message, run_agent  # noqa: E402
from app.agent.guidance import INSUFFICIENT_EVIDENCE_MESSAGE, classify_guidance, guidance_message  # noqa: E402


@pytest.mark.parametrize(("message", "kind"), [
    ("chào bạn", "greeting"),
    ("Chào", "greeting"),
    ("Xin chào DiaCare!", "greeting"),
    ("chao ban", "greeting"),
    ("hello", "greeting"),
    ("hi bạn ơi", "greeting"),
    ("cảm ơn bạn", "thanks"),
    ("thanks", "thanks"),
    ("tạm biệt nhé", "goodbye"),
    ("hướng dẫn", "usage"),
    ("bạn là ai?", "usage"),
    ("Bạn làm được gì?", "usage"),
    ("chào bạn, bạn giúp được gì?", "usage"),
    ("tôi nên hỏi gì", "usage"),
    ("giúp tôi với", "usage"),
    ("giải thích kết quả xét nghiệm", "lab_input"),
    ("xem chỉ số HbA1c của tôi", "lab_input"),
    ("kiểm tra đường huyết giúp tôi", "lab_input"),
    ("kết quả xét nghiệm của tôi thế nào", "lab_input"),
])
def test_whole_message_guidance_is_recognized(message, kind):
    assert classify_guidance(message) == kind


@pytest.mark.parametrize("message", [
    "HbA1c là gì?",
    "Đái tháo đường típ 2 là gì?",
    "Chào bạn, HbA1c là gì?",
    "HbA1c 6.2%",
    "kiểm tra đường huyết khi nào?",
    "xét nghiệm glucose lúc đói 126 mg/dL",
    "kiểm tra glucose 126",
    "BMI là gì",
    "Bạn có thể giúp gì cho người bị đái tháo đường?",
    "",
])
def test_real_questions_are_not_answered_by_templates(message):
    assert classify_guidance(message) is None


def test_no_gold_question_is_captured_by_guidance():
    gold = json.loads((ROOT / "evaluation" / "rag" / "gold_questions.json").read_text(encoding="utf-8"))
    assert [case["id"] for case in gold["questions"] if classify_guidance(case["question"])] == []


def test_greeting_explains_usage_without_tools_or_llm():
    with patch("app.agent.graph.search_kb") as retrieval, patch("app.agent.graph.compose_answer") as compose:
        response = run_agent("chào bạn", None, None)
    retrieval.assert_not_called()
    compose.assert_not_called()
    assert response["status"] == "OK"
    assert response["answer_mode"] == "deterministic"
    assert response["tool_calls"] == [] and response["citations"] == []
    assert "HbA1c 6.2%" in response["answer"] and "70 kg, 170 cm" in response["answer"]
    assert "Không đủ thông tin" not in response["answer"]
    assert [step["step"] for step in response["trace"]] == ["safety_gate", "guidance", "output_validator"]


def test_lab_request_without_value_asks_for_input():
    with patch("app.agent.graph.search_kb") as retrieval:
        response = run_agent("giải thích kết quả xét nghiệm", None, None)
    retrieval.assert_not_called()
    assert response["status"] == "NEED_CLARIFICATION"
    assert "HbA1c 6.2%" in response["answer"] and "mg/dL" in response["answer"]


@pytest.mark.parametrize("message", [
    "chào bạn, tôi đau ngực và khó thở",
    "chào bạn, tôi nên tiêm bao nhiêu đơn vị insulin?",
])
def test_safety_routes_win_over_greeting(message):
    with patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": []}):
        response = run_agent(message, None, None)
    assert not any(step.get("step") == "guidance" for step in response["trace"])
    assert response["status"] in {"EMERGENCY", "CLINICAL_REVIEW", "SAFETY_UNCERTAIN"}


def test_usage_examples_are_routed_to_the_promised_tools():
    assert _route_message("HbA1c 6.2%")[1] == ["search_kb", "classify_lab"]
    assert _route_message("glucose lúc đói 126 mg/dL")[1] == ["search_kb", "classify_lab"]
    assert _route_message("70 kg, 170 cm")[1] == ["calculate_bmi"]
    assert _route_message("lịch sử đo")[1] == ["get_history"]
    assert _route_message("đánh giá hồ sơ")[1] == ["predict_risk"]


def test_selected_profile_is_mentioned_only_in_usage_replies():
    assert "hồ sơ mô phỏng, nên" in guidance_message("greeting", has_profile=True)
    assert "hồ sơ mô phỏng, nên" not in guidance_message("thanks", has_profile=True)
    assert "hồ sơ mô phỏng, nên" not in guidance_message("greeting")


def test_unanswerable_question_points_to_the_guide():
    with patch("app.agent.graph.search_kb", return_value={"status": "INSUFFICIENT_EVIDENCE", "evidence": []}):
        response = run_agent("Thời tiết hôm nay thế nào?", None, None)
    assert response["status"] == "DEGRADED"
    assert response["answer"] == INSUFFICIENT_EVIDENCE_MESSAGE
    assert "hướng dẫn" in response["answer"]


def test_risk_request_without_profile_asks_for_profile():
    response = run_agent("đánh giá hồ sơ", None, None)
    assert "Hãy chọn một hồ sơ mô phỏng" in response["answer"]
    assert "CSV" not in response["answer"]
