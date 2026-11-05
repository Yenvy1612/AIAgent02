from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.composer import SYSTEM_PROMPT, compose_from_approved_evidence  # noqa: E402
from app.agent.fusion import structured_fusion  # noqa: E402
from app.agent.graph import run_agent  # noqa: E402


def test_structured_fusion_keeps_model_rules_and_retrieval_separate():
    ml = {"model_score": 0.72, "predicted_class": 1}
    rules = {"status": "OK", "normalized_value_mg_dl": 126.13}
    evidence = [{"retrieval_score": 0.12, "document_id": "KB-01"}]
    result = structured_fusion(
        ml=ml, clinical_rules=rules, evidence=evidence,
        safety_level="NORMAL", profile_type="synthetic",
    )
    assert result == {
        "ml": ml, "clinical_rules": rules, "evidence": evidence,
        "safety_level": "NORMAL", "profile_type": "synthetic",
    }
    assert "confidence_score" not in result
    assert result["ml"]["model_score"] != result["evidence"][0]["retrieval_score"]


def test_agent_response_has_sadd_contract_and_lab_result_remains_distinct():
    response = run_agent("HbA1c 6.2%", None, None)
    assert set(("ml", "clinical_rules", "evidence", "safety_level", "profile_type")).issubset(response)
    assert response["ml"] == {"status": "NOT_REQUESTED"}
    assert response["clinical_rules"]["status"] == "OK"
    assert response["safety_level"] == response["safety"]["level"]
    assert response["profile_type"] is None


def test_composer_uses_sadd_prompt_and_only_approved_evidence(monkeypatch):
    monkeypatch.setenv("DIACARE_LLM_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("DIACARE_ANTHROPIC_MODEL", raising=False)
    response_body = {"content": [{"type": "text", "text": "Tóm tắt từ nguồn."}]}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return response_body

    evidence = [
        {
            "title": "Approved", "topic": "nutrition", "excerpt": "Approved excerpt.",
            "review_status": "approved", "license_status": "approved",
        },
        {
            "title": "Candidate", "topic": "nutrition", "excerpt": "Do not send candidate.",
            "review_status": "candidate", "license_status": "approved",
        },
    ]
    with patch("app.agent.composer.httpx.post", return_value=FakeResponse()) as request:
        result = compose_from_approved_evidence(evidence)
    payload = request.call_args.kwargs["json"]
    assert result["status"] == "OK"
    assert payload["model"] == "claude-sonnet-5-5"
    assert SYSTEM_PROMPT.startswith("SYSTEM: DIACARE AI v1.1 — EDUCATIONAL DEMO")
    assert "PHẠM VI:" in payload["system"] and "RAG:" in payload["system"]
    assert "RÀNG BUỘC COMPOSER" in payload["system"]
    assert "Approved excerpt." in payload["messages"][0]["content"]
    assert "Do not send candidate." not in payload["messages"][0]["content"]
    assert "test-key" not in payload["messages"][0]["content"]


def test_llm_remains_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DIACARE_LLM_ENABLED", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = compose_from_approved_evidence([{
        "title": "Approved", "excerpt": "Approved excerpt.",
        "review_status": "approved", "license_status": "approved",
    }])
    assert result["status"] == "FALLBACK"
    assert result["answer"] == ""
