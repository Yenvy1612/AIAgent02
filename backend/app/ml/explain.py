from __future__ import annotations

from typing import Any

from app.ml.features import FEATURES, MODEL_VERSION
from app.ml.preprocessing import prediction_frame


def explain_model(model: Any, features: dict[str, Any]) -> dict[str, Any]:
    try:
        import shap
        sample = prediction_frame(features)
        transformed = model.named_steps["preprocessor"].transform(sample)
        matrix = transformed.toarray() if hasattr(transformed, "toarray") else transformed
        classifier = model.named_steps["classifier"]
        if hasattr(classifier, "feature_importances_"):
            explainer = shap.TreeExplainer(classifier)
        elif hasattr(classifier, "coef_"):
            explainer = shap.LinearExplainer(classifier, matrix[: min(40, len(matrix))])
        else:
            explainer = shap.Explainer(classifier, matrix[: min(40, len(matrix))])
        values = explainer(matrix)
        contributions = values.values[0]
        if getattr(contributions, "ndim", 1) == 2:
            contributions = contributions[:, -1]
        names = model.named_steps["preprocessor"].get_feature_names_out().tolist()
        items = sorted(
            ({"feature": name, "contribution": float(value)} for name, value in zip(names, contributions)),
            key=lambda item: abs(item["contribution"]), reverse=True,
        )[:8]
        return {
            "status": "OK", "model_version": MODEL_VERSION, "usage": "research_only",
            "explanation_method": "SHAP", "contributions": items,
            "interpretation_limit": "Contributions describe model output and do not establish causation.",
        }
    except ImportError:
        return {"status": "EXPLAINER_NOT_INSTALLED", "usage": "research_only", "contributions": []}
    except Exception as exc:
        return {"status": "EXPLANATION_ERROR", "message": type(exc).__name__, "usage": "research_only", "contributions": []}
