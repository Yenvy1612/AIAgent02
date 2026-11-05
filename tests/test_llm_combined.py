from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import _llm_composer_node, run_agent  # noqa: E402


def _evidence(**updates):
    return {
        "citation_id": "C-source", "document_id": "KB-01", "chunk_id": "KB-01-001",
        "title": "Hướng dẫn đã duyệt", "source_url": "https://example.org/kb-01",
        "page": 4, "review_status": "approved", "license_status": "approved",
        "excerpt": "HbA1c phản ánh mức glucose trung bình trong thời gian dài.",
        **updates,
    }


def _citation(cited_text):
    return SimpleNamespace(
        type="char_location", document_index=0, cited_text=cited_text,
        start_char_index=0, end_char_index=len(cited_text),
    )


def test_combined_lab_and_kb_uses_masked_question_and_preserves_fact_lines(monkeypatch):
    evidence = _evidence()
    question = "HbA1c 6.2% phản ánh điều gì? DEMO-03"
    cited_text = evidence["excerpt"]
    response_body = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=cited_text, citations=[_citation(cited_text)])],
    )
    captured = {}

    def fake_create_message(config, documents, task_text):
        captured["documents"] = documents
        captured["task_text"] = task_text
        return {
            "response": response_body, "reason": "OK", "latency_ms": 42,
            "model": config.model, "input_tokens": 30, "output_tokens": 10,
            "stop_reason": "end_turn",
        }

    with patch("app.agent.graph.search_kb", return_value={"status": "OK", "evidence": [evidence]}):
        monkeypatch.setenv("DIACARE_LLM_ENABLED", "false")
        deterministic = run_agent(question, None, None)
        # Deterministic fallback ends with the selected excerpt and a source note;
        # the LLM path replaces those two pieces with its cited explanation.
        expected_fact_lines = "\n\n".join(deterministic["answer"].split("\n\n")[:-2])

        monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        with patch("app.llm.composer.create_message", side_effect=fake_create_message):
            response = run_agent(question, None, None)

    assert response["answer_mode"] == "llm_cited"
    assert response["answer"].startswith(expected_fact_lines + "\n\n")
    assert "[C1]" in response["answer"]
    assert response["citations"]
    assert response["trace"][-2]["step"] == "llm_composer"
    assert response["trace"][-2]["mode"] == "llm_cited"
    payload = str(captured)
    assert "6.2" not in payload and "DEMO-03" not in payload
    assert "[giá trị đã ẩn]" in captured["task_text"]
    trace = str(response["trace"])
    assert "DEMO-03" not in trace and "6.2" not in trace


def test_model_citation_labels_follow_merged_rule_citations(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    rule_citation = {
        "citation_id": "C-rule", "document_id": "KB-RULE", "chunk_id": "KB-RULE-001",
        "title": "Rule source", "source_url": "https://example.org/rule", "page": 1,
    }
    evidence = _evidence(chunk_id="KB-01-002")
    llm_citation = {key: evidence[key] for key in (
        "citation_id", "document_id", "chunk_id", "title", "source_url", "page",
    )}
    state = {
        "message": "Explain HbA1c", "results": {"search_kb": {}, "classify_lab": {}},
        "evidence": [evidence], "citations": [rule_citation], "status": "OK",
        "answer": "fixed", "deterministic_answer": "fixed", "fact_parts": ["HbA1c 6.2%"],
        "note_parts": [], "trace": [],
    }
    with patch("app.agent.graph.compose_answer", return_value={
        "ok": True, "reason": "OK", "answer": "Concept explanation [C1]",
        "citations": [llm_citation], "data_level": "masked_question",
    }):
        output = _llm_composer_node(state)
    assert "Concept explanation [C1]" in output["answer"]
    assert [citation["display_label"] for citation in output["citations"]] == ["C1"]
