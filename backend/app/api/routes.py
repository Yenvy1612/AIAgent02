from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import chat, clinical, demo_profiles, knowledge, ml
from app.api.dependencies import get_db
from app.database.repository import list_profiles
from app.database.session import SYNTHETIC_DATA_ANCHOR, SYNTHETIC_DATA_SEED, synthetic_data_fingerprint
from app.ml.predict import risk_model
from app.llm.config import health as composer_health
from app.rag.retriever import knowledge_base
from app.rag.web_search import web_search_health
from app.safety.classifier import CLASSIFIER_VERSION

router = APIRouter()


@router.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok", "version": "1.1.0-demo", "profile_count": len(list_profiles(db)),
        "model": risk_model.health(), "knowledge_base": knowledge_base.health(),
        "answer_composer": composer_health(),
        "web_search": web_search_health(),
        "safety": {
            "available": True,
            "classifier_status": f"{CLASSIFIER_VERSION}_curated_not_clinically_validated",
            "tier2_timeout_seconds": 1.0,
        },
        "data_policy": "synthetic_profiles_only",
        "synthetic_data": {
            "version": "demo-v1", "seed": SYNTHETIC_DATA_SEED,
            "anchor_date": SYNTHETIC_DATA_ANCHOR.date().isoformat(), "sha256": synthetic_data_fingerprint(),
        },
    }


router.include_router(chat.router)
router.include_router(demo_profiles.router)
router.include_router(ml.router)
router.include_router(clinical.router)
router.include_router(knowledge.router)
