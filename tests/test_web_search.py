from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import _validate_output_node, run_agent  # noqa: E402
from app.safety.keyword_rules import contains_medication_dose, redact_medication_sentences  # noqa: E402
from app.rag import web_search  # noqa: E402

GENERAL_QUESTION = "Người đái tháo đường có nên ăn trái cây không?"
OK_RESULT = {
    "status": "OK", "reason": None, "answer": "Nên chọn trái cây nguyên quả.",
    "sources": [{"url": "https://www.cdc.gov/a", "title": "CDC", "cited_text": "whole fruit"}],
    "attributions": ["Nội dung từ CDC được dùng lại."],
}
DOMAINS = ["who.int", "cdc.gov"]


@pytest.fixture
def web_enabled(monkeypatch):
    monkeypatch.setenv("DIACARE_WEB_SEARCH_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.agent.graph.search_kb",
        lambda **kwargs: {"status": "INSUFFICIENT_EVIDENCE", "evidence": [], "retrieval_mode": "local"},
    )
    mock = MagicMock(return_value=OK_RESULT)
    monkeypatch.setattr("app.agent.graph.search_web", mock)
    return mock


def test_web_answer_is_labelled_and_stays_out_of_approved_citations(web_enabled):
    result = run_agent(GENERAL_QUESTION, None, None)
    web_enabled.assert_called_once_with(GENERAL_QUESTION)
    assert result["status"] == "WEB_UNVERIFIED"
    assert result["answer"].startswith(web_search.WEB_UNVERIFIED_NOTICE)
    assert "Nội dung từ CDC" in result["answer"]
    assert result["web_sources"] == OK_RESULT["sources"]
    assert result["citations"] == [] and result["evidence"] == []


def test_web_is_not_called_when_disabled(web_enabled, monkeypatch):
    monkeypatch.setenv("DIACARE_WEB_SEARCH_ENABLED", "false")
    result = run_agent(GENERAL_QUESTION, None, None)
    web_enabled.assert_not_called()
    assert result["status"] == "DEGRADED" and result["web_sources"] == []


def test_dosing_excerpt_is_dropped_without_blocking_the_other_evidence(web_enabled, monkeypatch):
    base = {
        "document_id": "KB-X", "title": "T", "source_url": None, "page": 1, "topic": "diagnosis",
        "review_status": "approved", "license_status": "approved",
    }
    safe = {**base, "citation_id": "C1", "chunk_id": "KB-X-1", "excerpt": "HbA1c phản ánh glucose trung bình."}
    dosing = {**base, "citation_id": "C2", "chunk_id": "KB-X-2", "excerpt": "Tiêm insulin 10 đơn vị mỗi tối."}
    monkeypatch.setattr("app.agent.graph.search_kb", lambda **kwargs: {"status": "OK", "evidence": [safe, dosing]})
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["status"] == "OK"
    assert [citation["chunk_id"] for citation in result["citations"]] == ["KB-X-1"]
    assert "10 đơn vị" not in result["answer"]


GENERAL_SENTENCES = (
    "Đái tháo đường được chẩn đoán dựa vào glucose huyết tương lúc đói hoặc HbA1c theo tiêu chuẩn của hướng dẫn. "
    "Xét nghiệm cần được lặp lại vào một ngày khác nếu không có triệu chứng rõ ràng của tăng glucose huyết. "
    "Kết quả phải được đối chiếu với tình trạng lâm sàng của người bệnh tại cơ sở y tế."
)


def _evidence(excerpt: str, topic: str = "diagnosis") -> dict:
    return {
        "citation_id": "C1", "document_id": "KB-X", "chunk_id": "KB-X-1", "title": "T", "source_url": None,
        "page": 1, "topic": topic, "review_status": "approved", "license_status": "approved", "excerpt": excerpt,
    }


def test_general_text_survives_when_only_some_sentences_mention_a_dose(web_enabled, monkeypatch):
    excerpt = f"{GENERAL_SENTENCES} Tiêm insulin 10 đơn vị mỗi tối."
    monkeypatch.setattr("app.agent.graph.search_kb", lambda **kwargs: {"status": "OK", "evidence": [_evidence(excerpt)]})
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["status"] == "OK"
    assert [citation["chunk_id"] for citation in result["citations"]] == ["KB-X-1"]
    assert "HbA1c" in result["answer"]
    assert "10 đơn vị" not in result["answer"] and "insulin" not in result["answer"]
    assert "đã được lược bỏ" in result["answer"]
    assert result["evidence"][0]["excerpt_redacted"] is True
    assert "insulin" not in result["evidence"][0]["excerpt"]


@pytest.mark.parametrize("sentence", [
    "Tăng 2 đơn vị mỗi 3 ngày.",
    "Metformin 500 mg uống hai lần mỗi ngày.",
    "Give metformin 1000 mg 2 x daily.",
    "Dapagliflozin khởi trị với liều 5 mg.",
    "Liều khởi đầu là 0,2 IU/kg.",
    "Thuốc được dùng 1 lần mỗi ngày.",
    "Gliclazide 80 hai lần.",
    "Ngừng điều trị khi pH tăng lên > 7,0.",
    "Dùng kháng sinh đường tiêm cho nhiễm trùng nặng.",
    "Nên tiêm.",
    "Those patients should be given hypertonic glucose intravenously.",
])
def test_redaction_removes_every_dose_sentence(sentence):
    assert redact_medication_sentences(f"{GENERAL_SENTENCES} {sentence}") == GENERAL_SENTENCES


@pytest.mark.parametrize("topic", ["medication", "hospital", "complications"])
def test_medication_chapters_are_dropped_whole(web_enabled, monkeypatch, topic):
    excerpt = f"{GENERAL_SENTENCES} Tiêm insulin 10 đơn vị mỗi tối."
    monkeypatch.setattr(
        "app.agent.graph.search_kb", lambda **kwargs: {"status": "OK", "evidence": [_evidence(excerpt, topic)]},
    )
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["citations"] == [] and "HbA1c" not in result["answer"]


def test_mostly_dosing_excerpt_is_dropped_whole(web_enabled, monkeypatch):
    excerpt = f"{GENERAL_SENTENCES} " + "Tiêm insulin 10 đơn vị mỗi tối. " * 30
    monkeypatch.setattr("app.agent.graph.search_kb", lambda **kwargs: {"status": "OK", "evidence": [_evidence(excerpt)]})
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["citations"] == [] and "HbA1c" not in result["answer"]


def test_antibiotic_regimen_tables_are_not_shown(web_enabled, monkeypatch):
    table = "PHÁC ĐỒ KHÁNG SINH THEO KINH NGHIỆM\nĐộ nhẹ: amoxicillin clavulanate\nĐộ vừa: ampicillin sulbactam"
    monkeypatch.setattr("app.agent.graph.search_kb", lambda **kwargs: {"status": "OK", "evidence": [_evidence(table, "foot_care")]})
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["citations"] == [] and "amoxicillin" not in result["answer"]


@pytest.mark.parametrize("message", ["Nên dùng kháng sinh gì cho loét bàn chân?", "Hạ đường huyết thì tiêm glucagon bao nhiêu?"])
def test_antibiotic_and_glucagon_questions_are_refused(message):
    result = run_agent(message, None, None)
    assert result["status"] == "CLINICAL_REVIEW" and result["citations"] == []


def test_glucose_tolerance_criteria_are_not_treated_as_a_dose():
    criterion = "Glucose huyết tương sau 2 giờ làm nghiệm pháp dung nạp với 75g glucose bằng đường uống ≥ 200 mg/dL."
    assert not contains_medication_dose(criterion)
    assert contains_medication_dose("Dùng 75g thuốc mỗi ngày.")


def test_the_output_guard_still_blocks_a_dose_in_the_final_answer():
    state = {
        "answer": "Tăng 2 đơn vị mỗi 3 ngày.", "safety": {"level": "NORMAL"},
        "evidence": [], "citations": [], "tool_calls": [], "trace": [],
    }
    assert _validate_output_node(state)["safety"]["output_guard"] == "medication_advice_blocked"


def test_web_is_not_called_when_the_kb_has_evidence(web_enabled, monkeypatch):
    evidence = {
        "citation_id": "C1", "document_id": "KB-X", "chunk_id": "KB-X-1", "title": "T", "source_url": None,
        "page": 1, "topic": "nutrition", "excerpt": "Nội dung đã duyệt.",
        "review_status": "approved", "license_status": "approved",
    }
    monkeypatch.setattr("app.agent.graph.search_kb", lambda **kwargs: {"status": "OK", "evidence": [evidence]})
    result = run_agent(GENERAL_QUESTION, None, None)
    web_enabled.assert_not_called()
    assert result["citations"] and result["web_sources"] == []


@pytest.mark.parametrize("message", [
    "Tôi đang khó thở và đau ngực ngay lúc này.",
    "Người bệnh đang bất tỉnh và co giật, cần làm gì?",
    "Tôi nên tự tăng liều insulin bao nhiêu?",
    "Có thể ngừng metformin khi thấy khỏe không?",
    "Glucose 42",
    "HbA1c 6.8% có cao không?",
    "Glucose 7 mmol/L lúc đói có sao không?",
    "Tính BMI: 68 kg, 170 cm",
    "Giá cổ phiếu Apple hôm nay là bao nhiêu?",
    "Cách nấu phở bò ngon?",
    "Bệnh đái tháo đường của tôi, gọi 0912345678 để tư vấn",
    "Email tôi là a.b@example.com, đái tháo đường có chữa được không?",
    "Mẹ tôi 70 tuổi bị đái tháo đường nên ăn gì?",
])
def test_web_is_never_called_for_unsafe_personal_or_unrelated_messages(web_enabled, message):
    result = run_agent(message, None, None)
    web_enabled.assert_not_called()
    assert result["web_sources"] == []


def test_web_is_not_called_when_a_demo_profile_is_selected(web_enabled):
    run_agent(GENERAL_QUESTION, "DEMO-01", MagicMock())
    web_enabled.assert_not_called()


def test_web_medication_dose_is_blocked_by_the_output_guard(web_enabled):
    web_enabled.return_value = {**OK_RESULT, "answer": "Hãy tiêm insulin 10 đơn vị mỗi tối."}
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["status"] == "CLINICAL_REVIEW"
    assert "10 đơn vị" not in result["answer"]
    assert result["web_sources"] == []


@pytest.mark.parametrize("reason", ["TIMEOUT", "NO_VERIFIED_PASSAGE"])
def test_web_failure_falls_back_to_the_normal_refusal(web_enabled, reason):
    web_enabled.return_value = {"status": "UNAVAILABLE", "reason": reason, "answer": "", "sources": [], "attributions": []}
    result = run_agent(GENERAL_QUESTION, None, None)
    assert result["status"] == "DEGRADED"
    assert "Không đủ thông tin" in result["answer"]
    assert result["web_sources"] == []


def test_web_exception_falls_back_to_the_normal_refusal(web_enabled):
    web_enabled.side_effect = RuntimeError("boom")
    assert run_agent(GENERAL_QUESTION, None, None)["status"] == "DEGRADED"


def _text(text: str, *urls: str):
    citations = [SimpleNamespace(url=url, title="Title", cited_text="cited") for url in urls]
    return SimpleNamespace(type="text", text=text, citations=citations or None)


def test_only_passages_with_allowed_https_citations_are_kept():
    answer, sources = web_search._extract_verified_answer([
        SimpleNamespace(type="server_tool_use", name="web_search"),
        _text("Tôi sẽ tìm kiếm."),
        _text("Giữ lại đoạn này.", "https://www.who.int/a"),
        _text("Bỏ vì miền lạ.", "https://evil.example.com/a"),
        _text("Bỏ vì miền giả.", "https://who.int.evil.example/a"),
        _text("Bỏ vì không phải https.", "http://www.cdc.gov/a"),
        _text("Bỏ vì trộn nguồn.", "https://www.cdc.gov/a", "https://evil.example.com/b"),
    ], DOMAINS)
    assert answer == "Giữ lại đoạn này."
    assert [source["url"] for source in sources] == ["https://www.who.int/a"]


def _fake_client(monkeypatch, *responses):
    client = MagicMock()
    client.beta.messages.create.side_effect = list(responses)
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: client)
    return client


def _response(stop_reason: str, *content):
    return SimpleNamespace(stop_reason=stop_reason, content=list(content))


def test_search_web_sends_the_allowlist_and_only_the_query(monkeypatch):
    client = _fake_client(monkeypatch, _response("end_turn", _text("Trả lời.", "https://www.cdc.gov/a")))
    result = web_search.search_web("Câu hỏi chung")
    kwargs = client.beta.messages.create.call_args.kwargs
    tool = kwargs["tools"][0]
    assert tool["allowed_domains"] == web_search.load_allowed_domains()
    assert tool["allowed_callers"] == ["direct"]
    assert tool["max_uses"] == web_search.MAX_SEARCHES
    assert len(kwargs["messages"]) == 1 and "Câu hỏi chung" in kwargs["messages"][0]["content"]
    assert result["status"] == "OK" and any("CDC" in note for note in result["attributions"])


def test_search_web_continues_after_pause_turn(monkeypatch):
    paused = SimpleNamespace(type="server_tool_use", name="web_search")
    client = _fake_client(
        monkeypatch, _response("pause_turn", paused), _response("end_turn", _text("Xong.", "https://who.int/a")),
    )
    assert web_search.search_web("Câu hỏi")["status"] == "OK"
    assert client.beta.messages.create.call_count == 2


@pytest.mark.parametrize("response, reason", [
    (_response("refusal"), "STOP_REFUSAL"),
    (_response("max_tokens", _text("Cắt giữa chừng.", "https://who.int/a")), "STOP_MAX_TOKENS"),
    (_response("end_turn", _text("Không có nguồn.")), "NO_VERIFIED_PASSAGE"),
    (_response("end_turn", SimpleNamespace(
        type="web_search_tool_result",
        content=SimpleNamespace(type="web_search_tool_result_error", error_code="unavailable"),
    )), "NO_VERIFIED_PASSAGE"),
])
def test_search_web_treats_refusals_truncation_and_tool_errors_as_unavailable(monkeypatch, response, reason):
    _fake_client(monkeypatch, response)
    result = web_search.search_web("Câu hỏi")
    assert result["status"] == "UNAVAILABLE" and result["reason"] == reason and result["answer"] == ""


def test_search_web_handles_timeouts(monkeypatch):
    client = _fake_client(monkeypatch)
    client.beta.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
    assert web_search.search_web("Câu hỏi")["reason"] == "TIMEOUT"


def test_allowlist_excludes_sources_with_restrictive_terms():
    domains = web_search.load_allowed_domains()
    assert {"who.int", "cdc.gov"}.issubset(domains)
    assert not {"diabetes.org", "diabetesjournals.org", "niddk.nih.gov"}.intersection(domains)


def test_web_health_reports_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DIACARE_WEB_SEARCH_ENABLED", raising=False)
    health = web_search.web_search_health()
    assert health["enabled"] is False and health["data_policy"] == "no_external_query"
