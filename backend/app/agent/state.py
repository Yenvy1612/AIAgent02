from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    message: str
    profile_id: str | None
    db: Any
    safety: dict[str, Any]
    trace: list[dict[str, Any]]
    intent: str
    parsed: dict[str, Any]
    calls: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    results: dict[str, Any]
    evidence: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    reference_only: list[dict[str, Any]]
    web_sources: list[dict[str, Any]]
    answer: str
    deterministic_answer: str
    fact_parts: list[str]
    note_parts: list[str]
    answer_mode: str
    llm: dict[str, Any]
    status: str
    ml: dict[str, Any]
    clinical_rules: dict[str, Any]
    safety_level: str
    profile_type: str | None

