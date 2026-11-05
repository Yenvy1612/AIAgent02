from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


FALLBACK_MODE = "deterministic-evidence-extracts"
SYSTEM_PROMPT = Path(__file__).with_name("system_prompt.txt").read_text(encoding="utf-8").strip()
DEFAULT_MODEL = "claude-sonnet-5-5"


def compose_from_approved_evidence(evidence: list[dict[str, Any]]) -> dict[str, str]:
    """Optionally summarize approved public KB excerpts without sending user text or profile data."""
    enabled = os.getenv("DIACARE_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not enabled or not api_key or not evidence:
        return {"status": "FALLBACK", "mode": FALLBACK_MODE, "answer": ""}

    approved = [
        {
            "title": str(item.get("title", ""))[:300],
            "topic": str(item.get("topic", ""))[:100],
            "excerpt": str(item.get("excerpt", ""))[:5000],
        }
        for item in evidence
        if item.get("review_status") == "approved" and item.get("license_status") == "approved"
    ]
    if not approved:
        return {"status": "FALLBACK", "mode": FALLBACK_MODE, "answer": ""}

    payload = {
        "model": os.getenv("DIACARE_ANTHROPIC_MODEL", DEFAULT_MODEL),
        "max_tokens": 500,
        "system": SYSTEM_PROMPT + "\n\nRÀNG BUỘC COMPOSER: Chỉ được tóm tắt các đoạn evidence đã duyệt đính kèm. "
                   "Không thêm sự kiện hoặc kết luận ngoài evidence; không tạo citation, URL, tên nguồn hay số trang.",
        "messages": [{
            "role": "user",
            "content": "Hãy tóm tắt các đoạn tài liệu đã duyệt sau thành câu trả lời ngắn, dễ hiểu:\n"
                       + json.dumps(approved, ensure_ascii=False),
        }],
    }
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=float(os.getenv("DIACARE_LLM_TIMEOUT_SECONDS", "8.0")),
        )
        response.raise_for_status()
        body = response.json()
        answer = "\n".join(
            block.get("text", "") for block in body.get("content", [])
            if block.get("type") == "text" and block.get("text")
        ).strip()
        if answer:
            return {"status": "OK", "mode": "claude-evidence-only", "answer": answer}
    except Exception:
        # Never log request text, the API key, or provider error bodies.
        pass
    return {"status": "FALLBACK", "mode": FALLBACK_MODE, "answer": ""}


def composer_health() -> dict[str, Any]:
    enabled = os.getenv("DIACARE_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    key_configured = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    return {
        "provider": "anthropic" if enabled and key_configured else "disabled",
        "configured": enabled and key_configured,
        "model": os.getenv("DIACARE_ANTHROPIC_MODEL", DEFAULT_MODEL) if enabled and key_configured else None,
        "data_policy": "approved_kb_excerpts_only_no_user_text_or_profile_data",
    }
