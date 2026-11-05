from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import joblib

from app.core.config import MODEL_PATH
from app.ml.explain import explain_model
from app.ml.features import FEATURES, MODEL_VERSION, missing_features
from app.ml.preprocessing import prediction_frame


class RiskModel:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self._model = None
        self._load_error: str | None = None
        self._metadata: dict[str, Any] | None = None
        self._decision_threshold = 0.5
        self._load()

    def _load(self) -> None:
        if not self.model_path.exists():
            self._load_error = "No reviewed dataset has been used to train a model."
            return
        try:
            metadata_path = self.model_path.with_suffix(".json")
            if not metadata_path.is_file():
                raise ValueError("Model metadata is missing; threshold provenance is required.")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            artifact_hash = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
            if metadata.get("model_artifact_sha256") != artifact_hash:
                raise ValueError("Model artifact hash does not match its metadata.")
            threshold = float(metadata["decision_threshold"])
            if not 0 <= threshold <= 1:
                raise ValueError("Model decision threshold is outside [0, 1].")
            self._model = joblib.load(self.model_path)
            self._metadata = metadata
            self._decision_threshold = threshold
        except Exception as exc:
            self._model = None
            self._load_error = f"Model artifact could not be loaded: {type(exc).__name__}"

    @property
    def available(self) -> bool:
        return self._model is not None

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        missing = missing_features(features)
        if missing:
            return {"status": "INVALID_FEATURES", "missing_features": missing, "usage": "research_only"}
        if not self.available:
            return {
                "task": "current_diabetes_classification", "status": "MODEL_NOT_AVAILABLE",
                "model_version": MODEL_VERSION, "clinical_validation": False,
                "usage": "research_only", "message": "Chưa có mô hình đã huấn luyện từ dữ liệu nghiên cứu được rà soát.",
            }
        try:
            sample = prediction_frame(features)
            score = float(self._model.predict_proba(sample)[0][1])
            predicted = int(score >= self._decision_threshold)
            return {
                "task": "current_diabetes_classification", "status": "OK",
                "model_version": (self._metadata or {}).get("model_version", MODEL_VERSION),
                "model_score": round(score, 6), "decision_threshold": self._decision_threshold,
                "recall_target": (self._metadata or {}).get("recall_target"),
                "model_artifact_sha256": (self._metadata or {}).get("model_artifact_sha256"),
                "predicted_class": predicted, "clinical_validation": False,
                "usage": "research_only", "explanation_status": "available_from_training_artifact_if_present",
            }
        except Exception as exc:
            return {
                "task": "current_diabetes_classification", "status": "MODEL_ERROR",
                "model_version": MODEL_VERSION, "clinical_validation": False,
                "usage": "research_only", "message": f"Model inference failed ({type(exc).__name__}).",
            }

    def explain(self, features: dict[str, Any]) -> dict[str, Any]:
        if not self.available:
            return {"status": "MODEL_NOT_AVAILABLE", "usage": "research_only", "contributions": []}
        return explain_model(self._model, features)

    def health(self) -> dict[str, Any]:
        metadata_path = self.model_path.with_suffix(".json")
        metadata = None
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = {"status": "invalid_metadata"}
        return {
            "available": self.available,
            "model_version": (self._metadata or {}).get("model_version", MODEL_VERSION),
            "clinical_validation": False, "usage": "research_only",
            "metadata": metadata, "decision_threshold": self._decision_threshold if self.available else None,
            "reason": self._load_error if not self.available else None,
        }


risk_model = RiskModel()

