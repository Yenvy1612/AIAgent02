from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.graph import _parse_measurement, run_agent
from app.api.dependencies import get_db
from app.api.schemas import ChatInput
from app.database.repository import list_profiles
from app.safety.gate import evaluate_safety

router = APIRouter(prefix="/api/v1")


@router.post("/chat")
def chat(data: ChatInput, db: Session = Depends(get_db)):
    message = data.message.strip()
    parsed = _parse_measurement(message)
    safety = evaluate_safety(message, parsed.get("glucose_value"), parsed.get("glucose_unit"))
    if safety["level"] in {"EMERGENCY", "UNKNOWN", "CLINICAL_REVIEW", "UNIT_AMBIGUOUS"}:
        result = run_agent(message, None, db)
        result["request_id"] = data.session_id
        result["profile_type"] = None
        return result
    explicit = re.search(r"\b(DEMO-\d{2})\b", data.message, flags=re.IGNORECASE)
    requested_profile = explicit.group(1).upper() if explicit else data.demo_profile_id
    if requested_profile and not any(p["id"] == requested_profile for p in list_profiles(db)):
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "profile_id": requested_profile})
    result = run_agent(message, requested_profile, db)
    result["request_id"] = data.session_id
    result["profile_type"] = "synthetic" if requested_profile else None
    return result


@router.post("/safety/check")
def safety_check(data: ChatInput):
    """Evaluate the deterministic rules and local experimental classifier."""
    parsed = _parse_measurement(data.message)
    return evaluate_safety(data.message, parsed.get("glucose_value"), parsed.get("glucose_unit"))
