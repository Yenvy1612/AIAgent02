from __future__ import annotations

from typing import Any


def structured_fusion(
    *,
    ml: dict[str, Any] | None = None,
    clinical_rules: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    safety_level: str = "UNKNOWN",
    profile_type: str | None = None,
) -> dict[str, Any]:
    """Keep model, rule, and retrieval outputs separate; never combine their scores."""
    return {
        "ml": ml if ml is not None else {"status": "NOT_REQUESTED"},
        "clinical_rules": clinical_rules if clinical_rules is not None else {"status": "NOT_REQUESTED"},
        "evidence": evidence if evidence is not None else [],
        "safety_level": safety_level,
        "profile_type": profile_type,
    }
