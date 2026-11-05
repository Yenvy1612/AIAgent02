from __future__ import annotations

import time
from typing import Any

import anthropic

from app.llm.config import LLMConfig


def create_message(config: LLMConfig, documents: list[dict[str, Any]], task_text: str) -> dict[str, Any]:
    started = time.perf_counter()
    request_attempted = False
    try:
        client = anthropic.Anthropic(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            max_retries=1,
        )
        params: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "output_config": {"effort": config.effort},
            "system": _system_prompt(),
            "messages": [{"role": "user", "content": [*documents, {"type": "text", "text": task_text}]}],
        }
        if "haiku" not in config.model.lower():
            params.update({"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"})
        request_attempted = True
        response = client.beta.messages.create(**params)
        usage = getattr(response, "usage", None)
        return {
            "response": response,
            "reason": "OK",
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "model": getattr(response, "model", config.model),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "stop_reason": getattr(response, "stop_reason", None),
            "request_attempted": request_attempted,
        }
    except anthropic.RateLimitError:
        reason = "RATE_LIMITED"
    except anthropic.APITimeoutError:
        reason = "UNAVAILABLE"
    except anthropic.APIConnectionError:
        reason = "UNAVAILABLE"
    except anthropic.APIStatusError as error:
        reason = f"API_ERROR_{error.status_code}"
    except Exception:
        reason = "INTERNAL_ERROR"
    return {
        "response": None,
        "reason": reason,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "model": config.model,
        "input_tokens": None,
        "output_tokens": None,
        "stop_reason": None,
        "request_attempted": request_attempted,
    }


def _system_prompt() -> str:
    from pathlib import Path

    return Path(__file__).with_name("composer_system.txt").read_text(encoding="utf-8").strip()
