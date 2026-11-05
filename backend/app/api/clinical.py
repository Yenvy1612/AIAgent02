from __future__ import annotations

from fastapi import APIRouter

from app.agent.tools import calculate_bmi, classify_lab
from app.api.schemas import BMIInput, LabInput
from app.rag.retriever import knowledge_base

router = APIRouter(prefix="/api/v1")


@router.post("/clinical/classify")
def clinical_classify(data: LabInput):
    payload = data.model_dump()
    if payload.get("glucose_value") is not None and payload.get("glucose_unit") is None:
        return classify_lab(payload)
    search = knowledge_base.search(
        "QĐ 5481/QĐ-BYT mục 1.1 ngưỡng chẩn đoán HbA1c glucose lúc đói OGTT 2 giờ glucose bất kỳ",
        topic="diagnosis", top_k=5,
    )
    return classify_lab(payload, evidence=search.get("evidence", []))


@router.post("/clinical/bmi")
def bmi(data: BMIInput):
    return calculate_bmi(data.weight_kg, data.height_cm)
