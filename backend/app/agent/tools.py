from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.clinical.rules import interpret_labs
from app.database.repository import get_history, get_profile, serialize_profile
from app.ml.predict import risk_model
from app.rag.retriever import knowledge_base
from app.rag.web_search import search_web  # noqa: F401


def calculate_bmi(weight_kg: float, height_cm: float) -> dict[str, Any]:
    if weight_kg <= 0 or height_cm <= 0:
        return {"status": "INVALID_INPUT", "message": "Cân nặng và chiều cao phải lớn hơn 0."}
    height_m = height_cm / 100
    return {"status": "OK", "bmi": round(weight_kg / (height_m * height_m), 2), "unit": "kg/m2"}


def predict_risk(features: dict[str, Any], include_explanation: bool = False) -> dict[str, Any]:
    result = risk_model.predict(features)
    if include_explanation and result.get("status") == "OK":
        result["explanation"] = risk_model.explain(features)
    return result


def classify_lab(data: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return interpret_labs(data, evidence=evidence)


def search_kb(query: str, topic: str | None = None, top_k: int = 5) -> dict[str, Any]:
    return knowledge_base.search(query=query, topic=topic, top_k=top_k)


def tool_get_history(db: Session, profile_id: str) -> dict[str, Any]:
    return get_history(db, profile_id)


def profile_features(db: Session, profile_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profile = get_profile(db, profile_id)
    if profile is None:
        return None, None
    serialized = serialize_profile(profile)
    return serialized, {name: serialized[name] for name in ("age", "gender", "bmi", "hypertension", "heart_disease", "smoking_history")}

