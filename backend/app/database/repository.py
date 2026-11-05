from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import DemoProfile, GlucoseReading, LabResult


def serialize_profile(row: DemoProfile) -> dict:
    return {
        "id": row.id, "profile_code": row.profile_code, "display_name": row.display_name,
        "age": row.age, "gender": row.gender, "height_cm": row.height_cm,
        "weight_kg": row.weight_kg, "bmi": row.bmi, "hypertension": row.hypertension,
        "heart_disease": row.heart_disease, "smoking_history": row.smoking_history,
        "known_type2_diabetes": row.known_type2_diabetes, "data_origin": row.data_origin,
    }


def list_profiles(db: Session) -> list[dict]:
    rows = db.scalars(select(DemoProfile).order_by(DemoProfile.profile_code)).all()
    return [serialize_profile(row) for row in rows]


def get_profile(db: Session, profile_id: str) -> DemoProfile | None:
    return db.scalar(select(DemoProfile).where(DemoProfile.profile_code == profile_id))


def get_history(db: Session, profile_id: str) -> dict:
    profile = get_profile(db, profile_id)
    if profile is None:
        return {"status": "PROFILE_NOT_FOUND", "profile_id": profile_id, "readings": [], "labs": []}
    readings = db.scalars(
        select(GlucoseReading).where(GlucoseReading.profile_id == profile.id).order_by(GlucoseReading.measured_at)
    ).all()
    labs = db.scalars(
        select(LabResult).where(LabResult.profile_id == profile.id).order_by(LabResult.measured_at)
    ).all()
    return {
        "status": "OK", "profile": serialize_profile(profile), "profile_type": "synthetic",
        "readings": [{
            "measured_at": r.measured_at.isoformat(), "original_value": r.original_value,
            "original_unit": r.original_unit, "glucose_mg_dl": r.glucose_mg_dl,
            "measurement_type": r.measurement_type, "source_type": r.source_type,
        } for r in readings],
        "labs": [{
            "measured_at": l.measured_at.isoformat(), "test_type": l.test_type,
            "original_value": l.original_value, "original_unit": l.original_unit,
            "source_type": l.source_type,
        } for l in labs],
    }

