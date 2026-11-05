from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL, DATA_DIR
from app.database.models import Base, DemoProfile, GlucoseReading, LabResult


if DATABASE_URL.startswith("sqlite:"):
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
SYNTHETIC_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic_profiles" / "demo_v1.json"
_SYNTHETIC_DATA = json.loads(SYNTHETIC_DATA_PATH.read_text(encoding="utf-8"))
SYNTHETIC_DATA_SEED = int(_SYNTHETIC_DATA["seed"])
SYNTHETIC_DATA_ANCHOR = datetime.fromisoformat(_SYNTHETIC_DATA["anchor_date"])


def _synthetic_bundle() -> tuple[list[dict], list[dict], list[dict]]:
    profiles = [dict(row) for row in _SYNTHETIC_DATA["profiles"]]
    readings = [
        {**row, "measured_at": datetime.fromisoformat(row["measured_at"])}
        for row in _SYNTHETIC_DATA["readings"]
    ]
    labs = [
        {**row, "measured_at": datetime.fromisoformat(row["measured_at"])}
        for row in _SYNTHETIC_DATA["labs"]
    ]
    return profiles, readings, labs


def synthetic_data_fingerprint() -> str:
    profiles, readings, labs = _synthetic_bundle()
    payload = json.dumps(
        {"seed": SYNTHETIC_DATA_SEED, "anchor": SYNTHETIC_DATA_ANCHOR.isoformat(),
         "profiles": profiles, "readings": readings, "labs": labs},
        sort_keys=True, separators=(",", ":"),
        default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(DemoProfile.id).limit(1)):
            return
        profiles, readings, labs = _synthetic_bundle()
        for row in profiles:
            profile = DemoProfile(**row)
            db.add(profile)
        db.add_all(GlucoseReading(**reading) for reading in readings)
        db.add_all(LabResult(**lab) for lab in labs)
        db.commit()

