from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_approval import sha256_file  # noqa: E402
from evaluate import prepare_test_data  # noqa: E402


def analyze_artifact(artifact_path: Path, csv_path: Path, output_dir: Path, manifest_path: Path | None = None) -> dict:
    try:
        import shap
    except ImportError as exc:
        raise RuntimeError("Install the pinned SHAP dependency from ml_training/requirements.txt.") from exc

    model = joblib.load(artifact_path)
    metadata = json.loads(artifact_path.with_suffix(".json").read_text(encoding="utf-8"))
    artifact_hash = sha256_file(artifact_path)
    if artifact_hash != metadata.get("model_artifact_sha256"):
        raise ValueError("Model artifact SHA-256 does not match its metadata.")
    X_test, _, split_info = prepare_test_data(csv_path, metadata, manifest_path)
    preprocessor = model.named_steps["preprocessor"]
    classifier = model.named_steps["classifier"]
    transformed_test = preprocessor.transform(X_test)
    feature_names = list(preprocessor.get_feature_names_out())

    if hasattr(classifier, "feature_importances_"):
        explainer = shap.TreeExplainer(classifier)
        raw_values = explainer.shap_values(transformed_test)
    elif hasattr(classifier, "coef_"):
        background = transformed_test[: min(100, transformed_test.shape[0])]
        explainer = shap.LinearExplainer(classifier, background)
        raw_values = explainer.shap_values(transformed_test)
    else:
        raise TypeError(f"No supported SHAP explainer for {type(classifier).__name__}.")

    if isinstance(raw_values, list):
        values = np.asarray(raw_values[min(1, len(raw_values) - 1)])
    else:
        values = np.asarray(raw_values)
        if values.ndim == 3:
            values = values[:, :, min(1, values.shape[2] - 1)]
    if values.ndim != 2 or values.shape[1] != len(feature_names):
        raise ValueError("SHAP returned an unexpected feature/value shape.")
    importance = np.mean(np.abs(values), axis=0)
    ranked = sorted(
        ({"feature": name, "mean_absolute_shap_value": float(score)} for name, score in zip(feature_names, importance)),
        key=lambda item: item["mean_absolute_shap_value"], reverse=True,
    )
    report = {
        "status": "MEASURED",
        "model_version": metadata.get("model_version"),
        "model_artifact_sha256": artifact_hash,
        "dataset_sha256": metadata.get("dataset_sha256"),
        "split_fingerprint": split_info,
        "test_rows": int(len(X_test)),
        "method": "global mean absolute SHAP value on held-out test split",
        "global_importance": ranked,
        "interpretation": "SHAP describes how model inputs contribute to this model's output. Không suy luận nhân quả.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{metadata.get('model_version', 'model')}_shap.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["output_path"] = str(output_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute global SHAP explanations on a saved model's test split.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation" / "ml")
    args = parser.parse_args()
    print(json.dumps(analyze_artifact(args.artifact, args.csv, args.output_dir, args.manifest), indent=2))


if __name__ == "__main__":
    main()
