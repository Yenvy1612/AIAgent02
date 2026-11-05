from __future__ import annotations

from typing import Any

from app.llm.client import create_message
from app.llm.config import LLMConfig, get_config
from app.llm.privacy import mask_question
from app.llm.request_builder import build_request
from app.llm.validators import validate_response


def compose_answer(
    question: str,
    evidence: list[dict[str, Any]],
    *,
    config: LLMConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    if not config.configured:
        reason = config.errors[0] if config.errors else "DISABLED"
        return {"ok": False, "reason": reason, "answer": "", "citations": [], "data_level": config.data_level}

    privacy = mask_question(question) if config.data_level == "masked_question" else {
        "question": "", "masked": False, "truncated": False,
    }
    request = build_request(str(privacy["question"]), evidence, data_level=config.data_level)
    if not request["documents"]:
        return {"ok": False, "reason": "NO_APPROVED_EVIDENCE", "answer": "", "citations": [], "data_level": config.data_level}

    result = create_message(config, request["documents"], request["task_text"])
    metadata = {
        "data_level": config.data_level,
        "question_masked": bool(privacy["masked"]),
        "question_truncated": bool(privacy["truncated"]),
        "model": result.get("model"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "stop_reason": result.get("stop_reason"),
        "request_attempted": bool(result.get("request_attempted", False)),
    }
    if result.get("response") is None:
        return {"ok": False, "reason": result["reason"], "answer": "", "citations": [], **metadata}

    try:
        validated = validate_response(result["response"], request["evidence"])
    except Exception:
        return {"ok": False, "reason": "INTERNAL_ERROR", "answer": "", "citations": [], **metadata}
    return {**validated, **metadata}
