from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_MODEL = "claude-opus-5-5"
ALLOWED_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"}
ALLOWED_DATA_LEVELS = {"evidence_only", "masked_question"}
ALLOWED_EFFORTS = {"low", "medium", "high", "max", "xhigh"}


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    api_key: str
    model: str
    effort: str
    data_level: str
    timeout_seconds: float
    max_tokens: int
    errors: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.api_key) and not self.errors


def _read_bool(value: str, name: str, errors: list[str]) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    errors.append(f"INVALID_{name}")
    return False


def get_config() -> LLMConfig:
    errors: list[str] = []
    enabled = _read_bool(os.getenv("DIACARE_LLM_ENABLED", "false"), "DIACARE_LLM_ENABLED", errors)
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("DIACARE_ANTHROPIC_MODEL", DEFAULT_MODEL).strip()
    effort = os.getenv("DIACARE_LLM_EFFORT", "medium").strip().lower()
    data_level = os.getenv("DIACARE_LLM_DATA_LEVEL", "masked_question").strip().lower()

    try:
        timeout_seconds = float(os.getenv("DIACARE_LLM_TIMEOUT_SECONDS", "15"))
        if not 0.1 <= timeout_seconds <= 120:
            raise ValueError
    except ValueError:
        timeout_seconds = 15.0
        errors.append("INVALID_DIACARE_LLM_TIMEOUT_SECONDS")

    try:
        max_tokens = int(os.getenv("DIACARE_LLM_MAX_TOKENS", "16000"))
        if not 256 <= max_tokens <= 64000:
            raise ValueError
    except ValueError:
        max_tokens = 16000
        errors.append("INVALID_DIACARE_LLM_MAX_TOKENS")

    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL
        errors.append("INVALID_DIACARE_ANTHROPIC_MODEL")
    if effort not in ALLOWED_EFFORTS:
        errors.append("INVALID_DIACARE_LLM_EFFORT")
    if data_level not in ALLOWED_DATA_LEVELS:
        errors.append("INVALID_DIACARE_LLM_DATA_LEVEL")
    if enabled and not api_key:
        errors.append("ANTHROPIC_API_KEY_MISSING")

    return LLMConfig(
        enabled=enabled and not errors,
        api_key=api_key,
        model=model,
        effort=effort if effort in ALLOWED_EFFORTS else "medium",
        data_level=data_level if data_level in ALLOWED_DATA_LEVELS else "masked_question",
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        errors=tuple(errors),
    )


def health() -> dict[str, Any]:
    config = get_config()
    configured = config.configured
    return {
        "provider": "anthropic" if configured else "disabled",
        "enabled": configured,
        "configured": configured,
        "model": config.model if configured else None,
        "effort": config.effort,
        "data_level": config.data_level,
        "data_policy": (
            "masked_question_and_approved_redacted_kb_excerpts"
            if configured and config.data_level == "masked_question"
            else "approved_redacted_kb_excerpts_only" if configured
            else "llm_disabled_no_data_sent"
        ),
        "config_errors": list(config.errors),
    }
