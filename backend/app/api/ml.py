from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import RiskInput
from app.agent.tools import predict_risk
from app.ml.predict import risk_model

router = APIRouter(prefix="/api/v1")


@router.post("/ml/predict")
def ml_predict(data: RiskInput):
    result = predict_risk(data.model_dump())
    if result.get("status") == "INVALID_FEATURES":
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/ml/explain")
def ml_explain(data: RiskInput):
    return risk_model.explain(data.model_dump())
