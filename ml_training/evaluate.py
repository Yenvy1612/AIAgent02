from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_approval import DatasetApprovalError, sha256_file, validate_dataset_approval  # noqa: E402
from splitting import fingerprint_groups, split_fingerprint, split_indices  # noqa: E402
from train import FEATURES, metrics  # noqa: E402

LAB_COLUMNS = ["hbA1c_level", "blood_glucose_level"]


def prepare_test_data(csv_path: Path, metadata: dict, manifest_path: Path | None = None):
    source_hash = sha256_file(csv_path)
    if metadata.get("dataset_sha256") != source_hash:
        raise ValueError("Evaluation CSV SHA-256 does not match the model artifact metadata.")
    if metadata.get("dataset_approval_manifest_sha256"):
        manifest_path = manifest_path or ROOT / "ml_training" / "dataset_approval.json"
        approval, _, manifest_hash = validate_dataset_approval(csv_path, manifest_path)
        if manifest_hash != metadata["dataset_approval_manifest_sha256"]:
            raise DatasetApprovalError("Approval manifest SHA-256 differs from the model artifact metadata.")
        if approval.get("status") != "approved":
            raise DatasetApprovalError("Evaluation is blocked because the dataset manifest is not approved.")
    elif metadata.get("fixture_only") is not True:
        raise ValueError("Artifact lacks an approved dataset manifest and is not marked fixture_only.")

    raw = pd.read_csv(csv_path)
    raw = raw.drop_duplicates(subset=list(raw.columns)).copy()
    required = FEATURES + LAB_COLUMNS + ["diabetes"]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"Evaluation dataset is missing required columns: {missing}")
    data = raw[list(dict.fromkeys(required + (["year"] if "year" in raw.columns else [])))].copy()
    for column in ["age", "bmi", "hypertension", "heart_disease", *LAB_COLUMNS]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data[data["age"].isna() | (data["age"] >= 18)].copy()
    data["diabetes"] = data["diabetes"].replace({True: 1, False: 0, "True": 1, "False": 0})
    data["diabetes"] = pd.to_numeric(data["diabetes"], errors="coerce")
    data = data[data["diabetes"].isin([0, 1])].copy()
    y = data["diabetes"].astype(int)
    fingerprint_columns = FEATURES + LAB_COLUMNS
    groups = fingerprint_groups(data, fingerprint_columns)
    splits = split_indices(data, y, None, None, fingerprint_columns=fingerprint_columns)
    split_info = split_fingerprint(splits, groups)
    expected_fingerprint = metadata.get("split_fingerprint", {}).get("sha256")
    if expected_fingerprint != split_info["sha256"]:
        raise ValueError("Evaluation split fingerprint does not match the training artifact.")
    test_ids = splits["test"]
    return data.loc[test_ids, FEATURES], y.loc[test_ids], split_info


def evaluate_artifact(artifact_path: Path, csv_path: Path, output_dir: Path, manifest_path: Path | None = None) -> dict:
    model = joblib.load(artifact_path)
    metadata_path = artifact_path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    actual_artifact_hash = sha256_file(artifact_path)
    if actual_artifact_hash != metadata.get("model_artifact_sha256"):
        raise ValueError("Model artifact SHA-256 does not match its metadata.")
    X_test, y_test, split_info = prepare_test_data(csv_path, metadata, manifest_path)
    probabilities = model.predict_proba(X_test)[:, 1]
    threshold = float(metadata.get("decision_threshold", 0.5))
    prediction = (probabilities >= threshold).astype(int)
    evaluation_metrics = metrics(y_test, prediction, probabilities)
    fpr, tpr, roc_thresholds = roc_curve(y_test, probabilities)
    precision, recall, pr_thresholds = precision_recall_curve(y_test, probabilities)
    observed, predicted = calibration_curve(y_test, probabilities, n_bins=min(10, max(2, len(y_test))), strategy="uniform")
    report = {
        "status": "MEASURED",
        "model_version": metadata.get("model_version"),
        "model_artifact_sha256": actual_artifact_hash,
        "dataset_sha256": metadata.get("dataset_sha256"),
        "split_fingerprint": split_info,
        "test_rows": int(len(y_test)),
        "decision_threshold": threshold,
        "metrics": evaluation_metrics,
        "confusion_matrix": confusion_matrix(y_test, prediction, labels=[0, 1]).tolist(),
        "roc_curve": [
            {"false_positive_rate": float(x), "true_positive_rate": float(y), "threshold": float(t)}
            for x, y, t in zip(fpr, tpr, roc_thresholds)
        ],
        "precision_recall_curve": [
            {"precision": float(p), "recall": float(r), "threshold": float(pr_thresholds[i]) if i < len(pr_thresholds) else None}
            for i, (p, r) in enumerate(zip(precision, recall))
        ],
        "calibration_curve": [
            {"mean_predicted_probability": float(p), "observed_positive_fraction": float(o)}
            for p, o in zip(predicted, observed)
        ],
        "brier_score": evaluation_metrics["brier_score"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(metadata.get("model_version", "model")))
    output_path = output_dir / f"{slug}_evaluation.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["output_path"] = str(output_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a research-only saved DiaCare model on its frozen test split.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evaluation" / "ml")
    args = parser.parse_args()
    print(json.dumps(evaluate_artifact(args.artifact, args.csv, args.output_dir, args.manifest), indent=2))


if __name__ == "__main__":
    main()
