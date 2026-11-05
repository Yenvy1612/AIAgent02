from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.database.repository import get_history, list_profiles

router = APIRouter(prefix="/api/v1")


@router.get("/demo/profiles")
def profiles(db: Session = Depends(get_db)):
    return {"items": list_profiles(db), "profile_type": "synthetic"}


@router.get("/demo/profiles/{profile_id}/history")
def history(profile_id: str, db: Session = Depends(get_db)):
    result = get_history(db, profile_id)
    if result["status"] == "PROFILE_NOT_FOUND":
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "profile_id": profile_id})
    return result
