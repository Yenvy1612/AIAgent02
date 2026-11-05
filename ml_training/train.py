from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.calibration import calibration_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from splitting import (
    fingerprint_groups, resolve_split_columns, runtime_versions, split_fingerprint,
    split_indices, year_split_audit,
)
from dataset_approval import DatasetApprovalError, validate_dataset_approval


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["age", "gender", "bmi", "hypertension", "heart_disease", "smoking_history"]
NUMERIC = ["age", "bmi", "hypertension", "heart_disease"]
CATEGORICAL = ["gender", "smoking_history"]
EXPECTED_CATEGORIES = {
    "gender": {"Male", "Female", "Other"},
    "smoking_history": {"never", "former", "current", "not current", "ever", "No Info"},
}


def metrics(y_true, prediction, probabilities) -> dict:
    matrix = confusion_matrix(y_true, prediction, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in matrix.ravel())
    result = {
        "accuracy": float(accuracy_score(y_true, prediction)),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall_sensitivity": float(recall_score(y_true, prediction, zero_division=0)),
        "specificity": float(tn / (tn + fp)) if tn + fp else None,
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "confusion_matrix_tn_fp_fn_tp": [tn, fp, fn, tp],
    }
    try:
        result["roc_auc"] = float(roc_auc_score(y_true, probabilities))
    except ValueError:
        result["roc_auc"] = None
    observed_fraction, predicted_mean = calibration_curve(
        y_true, probabilities, n_bins=min(10, max(2, len(y_true))), strategy="uniform",
    )
    result["calibration_curve"] = [
        {"mean_predicted_probability": float(predicted), "observed_positive_fraction": float(observed)}
        for predicted, observed in zip(predicted_mean, observed_fraction)
    ]
    return result


def select_recall_threshold(y_true, probabilities, target_recall: float = 0.90) -> tuple[float, dict]:
    """Select the highest validation cutoff that still meets the research recall target."""
    labels = pd.Series(y_true).astype(int).to_numpy()
    scores = pd.Series(probabilities, dtype="float64").to_numpy()
    if not 0 < target_recall <= 1 or not len(labels) or len(labels) != len(scores):
        raise ValueError("Threshold selection requires aligned validation labels and probabilities.")
    positive_scores = sorted(scores[labels == 1], reverse=True)
    if not positive_scores:
        raise ValueError("Threshold selection requires positive validation examples.")
    required_positives = max(1, int(math.ceil(target_recall * len(positive_scores))))
    threshold = float(positive_scores[required_positives - 1])
    prediction = (scores >= threshold).astype(int)
    threshold_metrics = metrics(labels, prediction, scores)
    return threshold, {
        "target_recall": target_recall,
        "validation_recall": threshold_metrics["recall_sensitivity"],
        "validation_specificity": threshold_metrics["specificity"],
        "target_met": threshold_metrics["recall_sensitivity"] >= target_recall,
        "threshold": threshold,
    }


def subgroup_report(X, y_true, probabilities, threshold: float) -> dict:
    predicted = (probabilities >= threshold).astype(int)
    bands = pd.cut(
        pd.to_numeric(X["age"], errors="coerce"),
        bins=[17, 29, 44, 59, 121], labels=["18-29", "30-44", "45-59", "60+"],
        include_lowest=True,
    )
    result = {}
    for feature, values in (("gender", X["gender"]), ("age_band", bands)):
        values = values.astype("string").fillna("Unknown")
        result[feature] = {}
        for label in values.unique():
            mask = values == label
            count = int(mask.sum())
            if count < 100:
                result[feature][str(label)] = {"n": count, "status": "insufficient_n", "minimum_n": 100}
            else:
                result[feature][str(label)] = {
                    "n": count,
                    "metrics": metrics(y_true.loc[mask], predicted[mask.to_numpy()], probabilities[mask.to_numpy()]),
                }
    return result


def make_pipeline(classifier, feature_columns=FEATURES) -> Pipeline:
    categorical_columns = [column for column in feature_columns if column in CATEGORICAL]
    numeric_columns = [column for column in feature_columns if column not in CATEGORICAL]
    transformers = []
    if numeric_columns:
        transformers.append(("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric_columns))
    if categorical_columns:
        transformers.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]), categorical_columns))
    preprocess = ColumnTransformer(transformers)
    return Pipeline([("preprocessor", preprocess), ("classifier", classifier)])


def research_candidate_estimators(y_train) -> dict[str, object]:
    """Build the reviewed baseline set using training-only class balance."""
    from xgboost import XGBClassifier

    labels = pd.Series(y_train).astype(int)
    positives = max(1, int((labels == 1).sum()))
    negatives = int((labels == 0).sum())
    return {
        "logistic_regression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=42,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=350, min_samples_leaf=2,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=350, max_depth=4, learning_rate=0.05, subsample=0.85,
            colsample_bytree=0.85, eval_metric="logloss", random_state=42,
            scale_pos_weight=negatives / positives, n_jobs=-1,
        ),
    }


def run_fixture_pipeline(raw: pd.DataFrame, artifact_path: Path) -> dict:
    """Train/evaluate a small-schema fixture without consulting dataset approval.

    This helper is exclusively for deterministic pipeline tests. Production entry
    points still call validate_dataset_approval before fitting any real dataset.
    """
    import hashlib

    lab_columns = ["hbA1c_level", "blood_glucose_level"]
    required = set(FEATURES + lab_columns + ["diabetes"])
    if not required.issubset(raw.columns):
        raise ValueError(f"Fixture is missing columns: {sorted(required - set(raw.columns))}")
    full_columns = list(raw.columns)
    duplicates = int(raw.duplicated(subset=full_columns).sum())
    data = raw.drop_duplicates(subset=full_columns).copy()
    data = data[data["age"] >= 18].copy()
    data["diabetes"] = pd.to_numeric(data["diabetes"], errors="coerce")
    data = data[data["diabetes"].isin([0, 1])].copy()
    fingerprint_columns = FEATURES + lab_columns
    groups = fingerprint_groups(data, fingerprint_columns)
    y = data["diabetes"].astype(int)
    splits = split_indices(data, y, None, None, fingerprint_columns=fingerprint_columns)
    X_train, X_validation, X_test = (data.loc[splits[name], FEATURES] for name in ("train", "validation", "test"))
    y_train, y_validation, y_test = (y.loc[splits[name]] for name in ("train", "validation", "test"))
    model = make_pipeline(LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))
    model.fit(X_train, y_train)
    validation_probability = model.predict_proba(X_validation)[:, 1]
    threshold, threshold_report = select_recall_threshold(y_validation, validation_probability, 0.90)
    test_probability = model.predict_proba(X_test)[:, 1]
    test_prediction = (test_probability >= threshold).astype(int)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_path)
    artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    dataset_bytes = raw.to_csv(index=False).encode("utf-8")
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
    split_info = split_fingerprint(splits, groups)
    metadata = {
        "model_version": f"risk-no-labs-fixture-{artifact_hash[:12]}",
        "model_artifact_sha256": artifact_hash,
        "dataset_sha256": dataset_hash,
        "dataset_approval_manifest_sha256": None,
        "fixture_only": True,
        "data_category": "synthetic",
        "usage": "research_only",
        "clinical_validation": False,
        "features": FEATURES,
        "fingerprint_columns": fingerprint_columns,
        "fingerprint_group_count": int(groups.nunique()),
        "exact_duplicate_rows_removed_across_all_original_columns": duplicates,
        "split_fingerprint": split_info,
        "split_strategy": "group_shuffle_split_feature_lab_fingerprint",
        "train_rows": len(X_train),
        "validation_rows": len(X_validation),
        "test_rows": len(X_test),
        "decision_threshold": threshold,
        "recall_target": 0.90,
        "recall_target_achieved_on_validation": threshold_report["target_met"],
        "threshold_selection": threshold_report,
        "test_metrics": metrics(y_test, test_prediction, test_probability),
        "random_seed": 42,
    }
    artifact_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train research-only current-diabetes classification baselines.")
    parser.add_argument("csv", type=Path, help="Public research dataset CSV; not synthetic demo profiles")
    parser.add_argument("--label-column", default="diabetes")
    parser.add_argument("--group-column", help="Person/patient ID column, when present")
    parser.add_argument("--time-column", help="Measurement/date column, when present")
    parser.add_argument("--output", type=Path, default=ROOT / "models" / "risk_no_labs.joblib")
    parser.add_argument("--approval-manifest", type=Path, default=ROOT / "ml_training" / "dataset_approval.json",
                        help="Reviewed JSON manifest binding rights and synthetic provenance to the dataset SHA-256")
    parser.add_argument("--confirm-feature-contract", action="store_true", help="Confirm actual CSV schema/categories were reviewed against the six-feature contract")
    args = parser.parse_args()
    if not args.confirm_feature_contract:
        parser.error("Review actual columns and categories, then pass --confirm-feature-contract.")
    source = args.csv.resolve()
    if not source.is_file():
        parser.error(f"CSV not found: {source}")
    try:
        approval, dataset_hash, approval_manifest_hash = validate_dataset_approval(source, args.approval_manifest.resolve())
    except DatasetApprovalError as exc:
        parser.error(str(exc))
    if approval.get("label_column") != args.label_column:
        parser.error("The approved manifest label_column does not match --label-column.")
    raw = pd.read_csv(source)
    group_column, time_column = resolve_split_columns(raw.columns, args.group_column, args.time_column, parser)
    print("Observed columns and dtypes:")
    print(raw.dtypes.to_string())
    print("Observed category values:")
    for column in CATEGORICAL:
        print(f"  {column}: {sorted(raw[column].dropna().astype(str).unique().tolist()) if column in raw else 'MISSING'}")
    lab_columns = ["hbA1c_level", "blood_glucose_level"]
    required = set(FEATURES + lab_columns + [args.label_column])
    missing = sorted(required - set(raw.columns))
    if missing:
        parser.error(f"CSV schema does not match the reviewed feature/split contract. Missing: {missing}")
    if any(column in FEATURES + [args.label_column] for column in (group_column, time_column) if column):
        parser.error("Identifier/time columns must remain split metadata, not model features or the label.")
    for column, allowed in EXPECTED_CATEGORIES.items():
        observed = set(raw[column].dropna().astype(str).unique())
        unexpected = sorted(observed - allowed)
        if unexpected:
            parser.error(f"Unexpected {column} categories {unexpected}; update and review the feature contract first.")

    full_row_columns = list(raw.columns)
    duplicates = int(raw.duplicated(subset=full_row_columns).sum())
    raw = raw.drop_duplicates(subset=full_row_columns).copy()
    fingerprint_columns = FEATURES + lab_columns
    included_columns = list(dict.fromkeys(
        FEATURES + lab_columns + [args.label_column]
        + [c for c in (group_column, time_column, "year") if c and c in raw.columns]
    ))
    data = raw[included_columns].copy()
    for column in NUMERIC + lab_columns:
        converted = pd.to_numeric(data[column], errors="coerce")
        invalid = data[column].notna() & converted.isna()
        if invalid.any():
            parser.error(f"Column {column} has non-numeric values; review the feature contract before training.")
        data[column] = converted
    data = data[data["age"].isna() | (data["age"] >= 18)]
    data[args.label_column] = data[args.label_column].replace({True: 1, False: 0, "True": 1, "False": 0})
    data[args.label_column] = pd.to_numeric(data[args.label_column], errors="coerce")
    data = data[data[args.label_column].isin([0, 1])]
    print(f"Exact duplicate rows removed across all original CSV columns: {duplicates}")
    if data[args.label_column].nunique() != 2 or data[args.label_column].value_counts().min() < 5:
        parser.error("Need at least five rows from each binary class after schema and duplicate review.")

    y = data[args.label_column].astype(int)
    year_audit = year_split_audit(data, y)
    try:
        splits = split_indices(data, y, group_column, time_column, fingerprint_columns=fingerprint_columns)
    except ValueError as exc:
        parser.error(str(exc))
    groups = fingerprint_groups(data, fingerprint_columns)
    split_info = split_fingerprint(splits, groups)
    X_train, X_val, X_test = (data.loc[splits[name], FEATURES] for name in ("train", "validation", "test"))
    y_train, y_val, y_test = (y.loc[splits[name]] for name in ("train", "validation", "test"))
    candidates = research_candidate_estimators(y_train)

    validation = {}
    fitted = {}
    thresholds = {}
    for name, estimator in candidates.items():
        pipeline = make_pipeline(estimator)
        pipeline.fit(X_train, y_train)
        probability = pipeline.predict_proba(X_val)[:, 1]
        threshold, threshold_report = select_recall_threshold(y_val, probability, target_recall=0.90)
        prediction = (probability >= threshold).astype(int)
        validation[name] = metrics(y_val, prediction, probability)
        validation[name]["decision_threshold_selection"] = threshold_report
        thresholds[name] = threshold
        fitted[name] = pipeline
        print(f"{name} validation: {json.dumps(validation[name])}")
    winner = max(validation, key=lambda name: validation[name]["pr_auc"])
    test_metrics_by_candidate = {}
    for name, model in fitted.items():
        test_probability = model.predict_proba(X_test)[:, 1]
        test_prediction = (test_probability >= thresholds[name]).astype(int)
        test_metrics_by_candidate[name] = metrics(y_test, test_prediction, test_probability)
        test_metrics_by_candidate[name]["decision_threshold"] = thresholds[name]
    chosen = fitted[winner]
    test_probability = chosen.predict_proba(X_test)[:, 1]
    test_prediction = (test_probability >= thresholds[winner]).astype(int)
    test_metrics = metrics(y_test, test_prediction, test_probability)
    subgroups = subgroup_report(X_test, y_test, test_probability, thresholds[winner])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(chosen, args.output)
    model_artifact_hash = hashlib.sha256(args.output.read_bytes()).hexdigest()
    metadata = {
        "model_version": f"risk-no-labs-v1-{model_artifact_hash[:12]}",
        "model_artifact_sha256": model_artifact_hash, "task": "current_diabetes_classification",
        "usage": "research_only", "clinical_validation": False,
        "fixture_only": False,
        "selected_candidate": winner, "features": FEATURES,
        "dataset_file_name": source.name, "dataset_sha256": dataset_hash,
        "dataset_approval_manifest_sha256": approval_manifest_hash,
        "dataset_source_url": approval["source_url"],
        "dataset_rights_basis": approval["rights_basis"],
        "data_category": approval["data_category"],
        "contains_real_patient_data": approval["contains_real_patient_data"],
        "permitted_use": approval["permitted_use"],
        "known_limitations": approval["known_limitations"],
        "dataset_label_definition": approval["label_definition"],
        "dataset_label_generation_method": approval["label_generation_method"],
        "dataset_reviewed_by": approval["reviewer"],
        "dataset_reviewed_at": approval["reviewed_at"],
        "training_script_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
        "runtime_versions": runtime_versions(),
        "train_rows": int(len(X_train)), "validation_rows": int(len(X_val)), "test_rows": int(len(X_test)),
        "exact_duplicate_rows_removed_across_all_original_columns": duplicates,
        "split_fingerprint": split_info,
        "fingerprint_columns": fingerprint_columns,
        "fingerprint_group_count": split_info["group_count"],
        "group_column": group_column, "time_column": time_column,
        "year_split_audit": year_audit,
        "split_strategy": "group_shuffle_split_feature_lab_fingerprint",
        "split_strategy_reason": "GroupShuffleSplit keeps identical six-feature plus two-lab fingerprints in one partition; year is audit metadata only and is excluded from model features.",
        "metrics_by_candidate_validation": validation, "selected_candidate_test_metrics": test_metrics,
        "metrics_by_candidate_held_out_test": test_metrics_by_candidate,
        "selected_candidate_test_subgroup_metrics": subgroups,
        "decision_threshold": thresholds[winner], "recall_target": 0.90,
        "recall_target_achieved_on_validation": validation[winner]["decision_threshold_selection"]["target_met"],
        "threshold_selection": validation[winner]["decision_threshold_selection"], "random_seed": 42,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "limits": ["research-only current-label classification", "not a future-risk forecast", "not clinically validated", "synthetic profiles were not used for training"],
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Selected candidate: {winner}")
    print(f"Held-out test metrics: {json.dumps(test_metrics)}")
    print(f"Saved artifact: {args.output}")


if __name__ == "__main__":
    main()
