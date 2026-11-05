from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("DIACARE_DATA_DIR", ROOT_DIR / "data"))
MODEL_PATH = Path(os.getenv("DIACARE_MODEL_PATH", ROOT_DIR / "models" / "risk_no_labs.joblib"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'diacare_demo.sqlite3').as_posix()}")
APP_ENV = os.getenv("APP_ENV", "local")
APP_VERSION = "1.1.0-demo"

