from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


SmokingHistory = Literal["never", "former", "current", "not current", "ever", "No Info"]


class RiskInput(BaseModel):
    age: int = Field(ge=18, le=120)
    gender: Literal["Male", "Female", "Other"]
    bmi: float = Field(gt=0, le=100)
    hypertension: Literal[0, 1]
    heart_disease: Literal[0, 1]
    smoking_history: SmokingHistory


class LabInput(BaseModel):
    hba1c_pct: float | None = Field(default=None, gt=0, le=30)
    glucose_value: float | None = Field(default=None, gt=0, le=2000)
    glucose_unit: Literal["mg/dL", "mmol/L"] | None = None
    measurement_type: Literal["fasting", "random", "ogtt_2h", "before_meal", "after_meal", "unknown"] = "unknown"
    fasting_confirmed: bool | None = None
    classic_symptoms: bool = False

    @model_validator(mode="after")
    def at_least_one_result(self):
        if self.hba1c_pct is None and self.glucose_value is None:
            raise ValueError("Provide HbA1c or glucose_value")
        return self


class SearchInput(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    topic: str | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class BMIInput(BaseModel):
    weight_kg: float = Field(gt=0, le=500)
    height_cm: float = Field(gt=0, le=260)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    demo_profile_id: str | None = Field(default=None, max_length=30)
    session_id: str | None = Field(default=None, max_length=80)

