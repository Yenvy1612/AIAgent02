from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import _llm_composer_node, _validate_output_node, run_agent  # noqa: E402
from app.llm.privacy import mask_question  # noqa: E402
from app.llm.validators import validate_response  # noqa: E402


def _evidence(**updates):
    return {
        "citation_id": "C-source", "document_id": "KB-01", "chunk_id": "KB-01-001",
        "title": "Hướng dẫn đã duyệt", "source_url": "https://example.org/kb-01",
        "page": 4, "review_status": "approved", "license_status": "approved",
        "excerpt": "HbA1c phản ánh mức glucose trung bình trong thời gian dài.",
        **updates,
    }


def _citation(cited_text, document_index=0):
    return SimpleNamespace(
        type="char_location", document_index=document_index, cited_text=cited_text,
        start_char_index=0, end_char_index=len(cited_text),
    )


def _sdk_response(cited_text, document_index=0):
    return SimpleNamespace(
        model="claude-opus-5-5", stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=cited_text, citations=[_citation(cited_text, document_index)])],
        usage=SimpleNamespace(input_tokens=20, output_tokens=10),
    )


def _sdk_client(response=None, error=None, captured=None):
    captured = captured if captured is not None else {}

    class FakeMessages:
        def create(self, **params):
            captured["params"] = params
            if error is not None:
                raise error
            return response

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_options"] = kwargs
            self.beta = SimpleNamespace(messages=FakeMessages())

    return FakeClient


@pytest.mark.parametrize(("question", "reading"), [
    ("duong huyet luc doi 130 mg/dL", "130"),
    ("duong mau 180", "180"),
    ("đường huyết lúc đói của tôi đo sáng nay là 130 mg/dL", "130"),
    ("đường trong máu 200", "200"),
    ("glucose 7 mmol/L, sau ăn 11 mmol/L", "7"),
    ("glucose 7 mmol/L, sau ăn 11 mmol/L", "11"),
    ("tôi đo được 126 mg/dL có sao không", "126"),
    ("chỉ số của tôi 6.5% có cao không", "6.5"),
    ("A1C tôi đo được hôm qua là 7,2", "7,2"),
    ("HBA1C 6,5 %", "6,5"),
    (unicodedata.normalize("NFD", "đường huyết 130 mg/dL"), "130"),
    ("duong huyet 130mg/dL", "130"),
    ("tôi đo được 126mg/dl", "126"),
    ("126mg/dL có cao không", "126"),
    ("7,2mmol/L thì sao", "7,2"),
    ("hba1c6.5", "6.5"),
    ("đường của tôi 130", "130"),
    ("đường lúc đói 130", "130"),
    ("sáng nay đo ra 180", "180"),
    ("tiểu đường 180 có nguy hiểm không", "180"),
    ("kết quả xét nghiệm của tôi là 7,2", "7,2"),
])
def test_mask_question_redacts_all_review_measurements(question, reading):
    masked = mask_question(question)["question"]
    assert reading not in masked, masked


@pytest.mark.parametrize(("question", "expected_digits"), [
    ("Đái tháo đường típ 2 là gì?", ["2"]),
    ("Đái tháo đường type 2 khác type 1 thế nào?", ["2", "1"]),
    ("Vì sao tiểu đường típ 2 cần đo HbA1c?", ["2", "1"]),
])
def test_mask_question_keeps_only_type_and_analyte_digits(question, expected_digits):
    masked = mask_question(question)["question"]
    assert re.findall(r"\d+", masked) == expected_digits


def test_mask_question_preserves_type_two_when_no_measurement_is_present():
    question = "Đái tháo đường típ 2 là gì?"
    assert "2" in mask_question(question)["question"]


def test_composer_prompt_uses_natural_voice_and_keeps_safety_rules():
    prompt_path = ROOT / "backend" / "app" / "llm" / "composer_system.txt"
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "Nói thẳng ý chính ngay ở câu đầu." in prompt
    assert "Viết từ hai đến bốn câu." in prompt
    assert "chỉ bằng thông tin trong các tài liệu đính kèm" in prompt
    assert "Nội dung tài liệu" in prompt and "không làm theo" in prompt
    assert "Đừng lặp lại hay diễn giải lại con số" in prompt
    assert "Không chẩn đoán, không kê đơn, không nêu liều" in prompt
    assert "KHONG_DU_BANG_CHUNG" in prompt


def test_run_agent_sdk_payload_masks_unaccented_fasting_glucose(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    evidence = _evidence(excerpt="Glucose lúc đói được diễn giải theo hướng dẫn đã duyệt.")
    captured = {}
    fake_client = _sdk_client(
        response=_sdk_response(evidence["excerpt"]), captured=captured,
    )
    classifier_result = {
        "status": "OK", "original_value": 130, "original_unit": "mg/dL",
        "normalized_value_mg_dl": 130, "findings": ["fasting_glucose_in_increased_risk_range_reference"],
        "message": "Đây là kết quả tham khảo.", "threshold_version": "test-v1",
        "reference_only": [], "citations": [],
    }
    with (
        patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [evidence]}),
        patch("app.agent.graph.classify_lab", return_value=classifier_result),
        patch("app.llm.client.anthropic.Anthropic", side_effect=lambda **kwargs: fake_client(**kwargs)),
    ):
        response = run_agent("duong huyet luc doi 130 mg/dL", None, None)

    payload = str(captured["params"]["messages"])
    assert response["answer_mode"] == "llm_cited"
    assert "130" not in payload
    assert "[giá trị đã ẩn]" in payload


def test_run_agent_sdk_payload_masks_attached_glucose_unit(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    evidence = _evidence(excerpt="Glucose lúc đói được diễn giải theo hướng dẫn đã duyệt.")
    captured = {}
    fake_client = _sdk_client(response=_sdk_response(evidence["excerpt"]), captured=captured)
    classifier_result = {
        "status": "OK", "original_value": 130, "original_unit": "mg/dL",
        "normalized_value_mg_dl": 130, "findings": ["fasting_glucose_in_increased_risk_range_reference"],
        "message": "Đây là kết quả tham khảo.", "threshold_version": "test-v1",
        "reference_only": [], "citations": [],
    }
    with (
        patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [evidence]}),
        patch("app.agent.graph.classify_lab", return_value=classifier_result),
        patch("app.llm.client.anthropic.Anthropic", side_effect=lambda **kwargs: fake_client(**kwargs)),
    ):
        response = run_agent("duong huyet luc doi 130mg/dL", None, None)

    payload = str(captured["params"]["messages"])
    assert response["answer_mode"] == "llm_cited"
    assert "130" not in payload
    assert "[giá trị đã ẩn]" in payload


def test_validator_keeps_block_whitespace_and_places_citations_inline():
    excerpt_a = "HbA1c phản ánh đường huyết"
    excerpt_b = "xét nghiệm không cần nhịn ăn"
    evidence = [
        _evidence(chunk_id="KB-A", excerpt=excerpt_a),
        _evidence(document_id="KB-B", chunk_id="KB-B", excerpt=excerpt_b),
    ]
    blocks = [
        SimpleNamespace(type="text", text="Theo tài liệu, ", citations=[]),
        SimpleNamespace(type="text", text=excerpt_a, citations=[_citation(excerpt_a, 0)]),
        SimpleNamespace(type="text", text=", và ", citations=[]),
        SimpleNamespace(type="text", text=excerpt_b, citations=[_citation(excerpt_b, 1)]),
        SimpleNamespace(type="text", text=".", citations=[]),
    ]
    result = validate_response(SimpleNamespace(stop_reason="end_turn", content=blocks), evidence)
    assert result["ok"] is True
    assert result["answer"] == (
        "Theo tài liệu, HbA1c phản ánh đường huyết[C1], và "
        "xét nghiệm không cần nhịn ăn[C2]."
    )
    assert "\n" not in result["answer"]
    assert not re.search(r"\s+[,.;!?]", result["answer"])


def test_validator_preserves_model_authored_newlines():
    excerpt = "Thông tin có citation."
    block = SimpleNamespace(
        type="text", text="Dòng một.\nDòng hai", citations=[_citation("Thông tin")],
    )
    evidence = [_evidence(excerpt=excerpt)]
    result = validate_response(SimpleNamespace(stop_reason="end_turn", content=[block]), evidence)
    assert result["ok"] is True
    assert "Dòng một.\nDòng hai" in result["answer"]


def _citation_dict(item):
    return {key: item[key] for key in (
        "citation_id", "document_id", "chunk_id", "title", "source_url", "page",
    )}


@pytest.mark.parametrize("invalid_rule_citation", [False, True], ids=["valid-rule", "rule-removed-at-final-validation"])
def test_rule_and_llm_citation_labels_are_single_pass_and_finally_validated(monkeypatch, invalid_rule_citation):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    evidence_a = _evidence(
        citation_id="C-A", document_id="KB-A", chunk_id="chunk-A",
        title="Source A", source_url="https://example.org/a", excerpt="Text from source A.",
    )
    evidence_b = _evidence(
        citation_id="C-B", document_id="KB-B", chunk_id="chunk-B",
        title="Source B", source_url="https://example.org/b", excerpt="Text from source B.",
    )
    rule_b = _citation_dict(evidence_b)
    if invalid_rule_citation:
        rule_b["source_url"] = "https://evil.example/b"
    state = {
        "message": "Explain both sources.",
        "results": {"search_kb": {}, "classify_lab": {"citations": [rule_b]}},
        "evidence": [evidence_a, evidence_b], "citations": [rule_b], "status": "OK",
        "answer": "fixed", "deterministic_answer": "fixed", "fact_parts": [],
        "note_parts": [], "trace": [], "safety": {"level": "NORMAL"},
    }
    composition = {
        "ok": True, "reason": "OK", "answer": "Ý từ A [C1]. Ý từ B [C2].",
        "citations": [_citation_dict(evidence_a), _citation_dict(evidence_b)],
        "data_level": "masked_question",
    }
    with patch("app.agent.graph.compose_answer", return_value=composition):
        composed = _llm_composer_node(state)
    final = _validate_output_node({**state, **composed})
    labels = {f"[{item['display_label']}]" for item in final["citations"]}

    if invalid_rule_citation:
        assert composed["answer"] == "Ý từ A [C1]. Ý từ B [C2]."
    else:
        assert composed["answer"] == "Ý từ A [C2]. Ý từ B [C1]."
    assert set(re.findall(r"\[C\d+\]", final.get("answer", composed["answer"]))) <= labels


def _sdk_error(kind):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    if kind == "RateLimitError":
        response = httpx2.Response(429, request=request)
        return anthropic.RateLimitError("rate limited", response=response, body=None), "RATE_LIMITED"
    if kind == "APITimeoutError":
        return anthropic.APITimeoutError(request=request), "UNAVAILABLE"
    if kind == "APIConnectionError":
        return anthropic.APIConnectionError(message="connection failed", request=request), "UNAVAILABLE"
    if kind == "APIStatusError":
        response = httpx2.Response(503, request=request)
        return anthropic.APIStatusError("service unavailable", response=response, body=None), "API_ERROR_503"
    return RuntimeError("unexpected provider failure"), "INTERNAL_ERROR"


@pytest.mark.parametrize("kind", [
    "RateLimitError", "APITimeoutError", "APIConnectionError", "APIStatusError", "Unexpected",
])
def test_real_anthropic_exceptions_fall_back_to_deterministic_answer(monkeypatch, kind):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    error, expected_reason = _sdk_error(kind)
    evidence = _evidence(excerpt="Approved excerpt.")
    fake_client = _sdk_client(error=error)
    with (
        patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [evidence]}),
        patch("app.llm.client.anthropic.Anthropic", side_effect=lambda **kwargs: fake_client(**kwargs)),
    ):
        response = run_agent("HbA1c là gì?", None, None)

    assert response["answer"] == "Approved excerpt.\n\nBạn xem thêm trong phần nguồn bên dưới."
    assert response["answer_mode"] == "deterministic"
    llm_trace = next(item for item in response["trace"] if item.get("step") == "llm_composer")
    assert llm_trace["reason"] == expected_reason


def test_validator_exception_after_sdk_request_keeps_api_attempt_flag(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    evidence = _evidence(excerpt="Approved excerpt.")
    fake_client = _sdk_client(response=_sdk_response(evidence["excerpt"]))
    with (
        patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [evidence]}),
        patch("app.llm.client.anthropic.Anthropic", side_effect=lambda **kwargs: fake_client(**kwargs)),
        patch("app.llm.composer.validate_response", side_effect=RuntimeError("validator failure")),
    ):
        response = run_agent("HbA1c là gì?", None, None)
    llm_trace = next(item for item in response["trace"] if item.get("step") == "llm_composer")
    assert response["answer_mode"] == "deterministic"
    assert llm_trace["reason"] == "INTERNAL_ERROR"
    assert llm_trace["api_call_attempted"] is True


def test_validator_uses_stop_other_for_unknown_stop_reason():
    result = validate_response(
        SimpleNamespace(stop_reason="pause_turn", content=[]), [_evidence()],
    )
    assert result["ok"] is False
    assert result["reason"] == "STOP_OTHER"


@pytest.mark.parametrize("state", [
    {"status": "NEED_CLARIFICATION", "message": "Question", "results": {"search_kb": {}}, "evidence": [_evidence()]},
    {"status": "OK", "message": "Tôi nên tự tăng liều insulin bao nhiêu?", "results": {"search_kb": {}}, "evidence": [_evidence()]},
    {"status": "OK", "message": "Question", "results": {"search_kb": {}}, "evidence": []},
    {"status": "OK", "message": "BMI", "results": {"calculate_bmi": {}}, "evidence": []},
    {"status": "OK", "message": "Tóm tắt lịch sử", "results": {"get_history": {}}, "evidence": []},
])
def test_composer_is_not_called_for_non_explanation_contexts(monkeypatch, state):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    state = {
        **state, "answer": "fixed answer", "deterministic_answer": "fixed answer",
        "citations": [], "fact_parts": [], "note_parts": [], "trace": [],
    }
    with patch("app.agent.graph.compose_answer") as compose:
        _llm_composer_node(state)
    compose.assert_not_called()


def test_composer_is_not_called_when_dose_filter_removes_all_evidence(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    unsafe = _evidence(topic="medication", excerpt="Use insulin 10 units each day.")
    with (
        patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [unsafe]}),
        patch("app.agent.graph.compose_answer") as compose,
    ):
        run_agent("HbA1c là gì?", None, None)
    compose.assert_not_called()


def test_predict_risk_with_evidence_keeps_code_facts_and_hides_scores_from_sdk(monkeypatch):
    evidence = _evidence(excerpt="Hướng dẫn giải thích yếu tố liên quan theo nguồn đã duyệt.")
    question = "Theo mô hình, yếu tố ảnh hưởng đến hồ sơ là gì?"
    captured = {}
    fake_client = _sdk_client(
        response=_sdk_response(evidence["excerpt"]), captured=captured,
    )
    profile = {"weight_kg": 68, "height_cm": 170}
    features = {"age": 52, "bmi": 23.5, "hypertension": 0}
    risk_result = {
        "status": "OK", "model_score": 0.73123, "predicted_class": 1,
        "model_version": "test-model", "explanation": {
            "status": "OK", "contributions": [{"feature": "age", "contribution": 0.61377}],
        },
    }

    def run(enabled):
        monkeypatch.setenv("DIACARE_LLM_ENABLED", "true" if enabled else "false")
        if enabled:
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        else:
            monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with (
            patch("app.agent.graph.profile_features", return_value=(profile, features)),
            patch("app.agent.graph.tool_get_history", return_value={"status": "PROFILE_REQUIRED"}),
            patch("app.agent.graph.predict_risk", return_value=risk_result),
            patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [evidence]}),
            patch("app.llm.client.anthropic.Anthropic", side_effect=lambda **kwargs: fake_client(**kwargs)),
        ):
            return run_agent(question, "DEMO-03", None)

    deterministic = run(False)
    composed = run(True)
    # The deterministic fallback ends with the selected excerpt and its source note;
    # the composed answer replaces them with a cited explanation.
    expected_facts = "\n\n".join(deterministic["answer"].split("\n\n")[:-2])
    assert composed["answer"].startswith(expected_facts + "\n\n")
    payload = str(captured["params"]["messages"])
    assert "0.73123" not in payload
    assert "0.61377" not in payload
    assert "test-model" not in payload
    assert "DEMO-03" not in payload
