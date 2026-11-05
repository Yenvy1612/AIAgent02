from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from sklearn.base import clone
from train import (
    CATEGORICAL, EXPECTED_CATEGORIES, FEATURES, make_pipeline, metrics,
    research_candidate_estimators, select_recall_threshold,
)
from splitting import fingerprint_groups, resolve_split_columns, runtime_versions, split_fingerprint, split_indices
from dataset_approval import DatasetApprovalError, validate_dataset_approval


ROOT = Path(__file__).resolve().parents[1]


def label_leakage_interpretation(positive_capture: float | None) -> str:
    if positive_capture is None:
        return (
            "No adult positive labels remain after filtering, so the proxy capture rate cannot be measured. "
            "With-labs metrics are not evidence of prospective predictive value."
        )
    if positive_capture >= 1.0:
        return (
            "The proxy rule captures 100% of adult positive labels in this dataset. With-labs AUC does not "
            "reflect prospective predictive value because label-generation history is undocumented and lab "
            "thresholds may leak the target."
        )
    return (
        f"The proxy rule captures {positive_capture:.1%} of adult positive labels in this dataset; "
        "that proxy alone does not establish the label-generation method. With-labs AUC is descriptive "
        "of this dataset and is not evidence of prospective predictive value."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired no-labs vs with-labs research experiment.")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--label-column", default="diabetes")
    parser.add_argument("--group-column", help="Person/patient ID column, when present")
    parser.add_argument("--time-column", help="Measurement/date column, when present")
    parser.add_argument("--lab-features", nargs="+", default=["hbA1c_level", "blood_glucose_level"], help="Exact HbA1c/glucose column names from inspected CSV")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "ml" / "no_labs_vs_with_labs.json")
    parser.add_argument("--approval-manifest", type=Path, default=ROOT / "ml_training" / "dataset_approval.json",
                        help="Reviewed JSON manifest binding rights and synthetic provenance to the dataset SHA-256")
    parser.add_argument("--confirm-feature-contract", action="store_true")
    args = parser.parse_args()
    if not args.confirm_feature_contract:
        parser.error("Review the actual CSV schema and categories, then confirm the feature contract.")
    source = args.csv.resolve()
    if not source.is_file():
        parser.error(f"CSV not found: {source}")
    try:
        approval, dataset_hash, approval_manifest_hash = validate_dataset_approval(
            source, args.approval_manifest.resolve(), require_label_leakage_review=True,
        )
    except DatasetApprovalError as exc:
        parser.error(str(exc))
    if approval.get("label_column") != args.label_column:
        parser.error("The approved manifest label_column does not match --label-column.")
    raw = pd.read_csv(source)
    group_column, time_column = resolve_split_columns(raw.columns, args.group_column, args.time_column, parser)
    print("Observed columns and dtypes:")
    print(raw.dtypes.to_string())
    for column, allowed in EXPECTED_CATEGORIES.items():
        if column not in raw:
            parser.error(f"CSV is missing categorical feature {column}.")
        unexpected = sorted(set(raw[column].dropna().astype(str).unique()) - allowed)
        if unexpected:
            parser.error(f"Unexpected {column} categories {unexpected}; update and review the contract first.")
    with_features = FEATURES + args.lab_features
    if any(column in with_features + [args.label_column] for column in (group_column, time_column) if column):
        parser.error("Identifier/time columns must remain split metadata, not model features or the label.")
    required = set(with_features + [args.label_column])
    missing = sorted(required - set(raw.columns))
    if missing:
        parser.error(f"CSV is missing required columns: {missing}")
    if len(set(with_features)) != len(with_features):
        parser.error("Lab features must be distinct from the six no-labs features and from each other.")
    full_row_columns = list(raw.columns)
    duplicates = int(raw.duplicated(subset=full_row_columns).sum())
    raw = raw.drop_duplicates(subset=full_row_columns).copy()
    fingerprint_columns = FEATURES + args.lab_features
    included_columns = list(dict.fromkeys(
        with_features + [args.label_column]
        + [c for c in (group_column, time_column, "year") if c and c in raw.columns]
    ))
    data = raw[included_columns].copy()
    for column in FEATURES:
        if column in CATEGORICAL:
            continue
        converted = pd.to_numeric(data[column], errors="coerce")
        invalid = data[column].notna() & converted.isna()
        if invalid.any():
            parser.error(f"Column {column} has non-numeric values; update the reviewed contract first.")
        data[column] = converted
    for column in args.lab_features:
        converted = pd.to_numeric(data[column], errors="coerce")
        invalid = data[column].notna() & converted.isna()
        if invalid.any():
            parser.error(f"Lab column {column} contains non-numeric or mixed-unit values; normalize units before comparison.")
        data[column] = converted
    data = data[data["age"].isna() | (pd.to_numeric(data["age"], errors="coerce") >= 18)]
    data[args.label_column] = data[args.label_column].replace({True: 1, False: 0, "True": 1, "False": 0})
    data[args.label_column] = pd.to_numeric(data[args.label_column], errors="coerce")
    data = data[data[args.label_column].isin([0, 1])]
    y = data[args.label_column].astype(int)
    if y.nunique() != 2 or y.value_counts().min() < 5:
        parser.error("Need at least five rows from each binary class after filtering.")
    try:
        splits = split_indices(data, y, group_column, time_column, fingerprint_columns=fingerprint_columns)
    except ValueError as exc:
        parser.error(str(exc))
    train_ids, validation_ids, test_ids = (splits[name] for name in ("train", "validation", "test"))
    groups = fingerprint_groups(data, fingerprint_columns)
    split_info = split_fingerprint(splits, groups)
    candidates = research_candidate_estimators(y.loc[train_ids])

    all_results = {}
    for label, columns in (("risk_without_labs", FEATURES), ("classifier_with_labs", with_features)):
        by_model = {}
        fitted = {}
        thresholds = {}
        for model_name, estimator in candidates.items():
            pipeline = make_pipeline(clone(estimator), columns)
            pipeline.fit(data.loc[train_ids, columns], y.loc[train_ids])
            val_prob = pipeline.predict_proba(data.loc[validation_ids, columns])[:, 1]
            threshold, threshold_report = select_recall_threshold(y.loc[validation_ids], val_prob, 0.90)
            val_pred = (val_prob >= threshold).astype(int)
            val_metrics = metrics(y.loc[validation_ids], val_pred, val_prob)
            val_metrics["decision_threshold_selection"] = threshold_report
            thresholds[model_name] = threshold
            fitted[model_name] = pipeline
            by_model[model_name] = {"validation": val_metrics}
        winner = max(by_model, key=lambda name: by_model[name]["validation"]["pr_auc"])
        for model_name, model in fitted.items():
            # Use the same train-fitted estimator that produced validation scores;
            # this keeps the validation threshold calibrated for the tested model.
            selected = model
            test_prob = selected.predict_proba(data.loc[test_ids, columns])[:, 1]
            test_pred = (test_prob >= thresholds[model_name]).astype(int)
            by_model[model_name]["held_out_test"] = metrics(y.loc[test_ids], test_pred, test_prob)
            by_model[model_name]["held_out_test"]["decision_threshold"] = thresholds[model_name]
        all_results[label] = {
            "features": columns, "selected_candidate_by_validation_pr_auc": winner,
            "candidates": by_model,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    proxy_positive = (data["hbA1c_level"] >= 6.5) | (data["blood_glucose_level"] >= 126)
    positive_rows = y == 1
    positive_count = int(positive_rows.sum())
    captured_positives = int((proxy_positive & positive_rows).sum())
    positive_capture = captured_positives / positive_count if positive_count else None
    false_positive_rows = int((proxy_positive & (y == 0)).sum())
    output = {
        "status": "MEASURED", "dataset": source.name,
        "dataset_sha256": dataset_hash,
        "dataset_approval_manifest_sha256": approval_manifest_hash,
        "dataset_source_url": approval["source_url"],
        "dataset_rights_basis": approval["rights_basis"],
        "data_category": approval["data_category"],
        "contains_real_patient_data": approval["contains_real_patient_data"],
        "permitted_use": approval["permitted_use"],
        "dataset_label_definition": approval["label_definition"],
        "dataset_label_generation_method": approval["label_generation_method"],
        "dataset_reviewed_by": approval["reviewer"],
        "dataset_reviewed_at": approval["reviewed_at"],
        "label_leakage_reviewed": approval["label_leakage_reviewed"],
        "label_leakage_review_notes": approval["label_leakage_review_notes"],
        "comparison_script_sha256": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest(),
        "runtime_versions": runtime_versions(),
        "feature_contract_reviewed_by_operator": True,
        "shared_split_for_both_feature_sets": True,
        "validation_recall_target": 0.90,
        "person_grouped_split": bool(group_column), "random_seed": 42,
        "rows_after_filtering": int(len(data)), "exact_duplicate_rows_removed_across_all_original_columns": duplicates,
        "train_rows": int(len(train_ids)), "validation_rows": int(len(validation_ids)), "test_rows": int(len(test_ids)),
        "group_column": group_column, "time_column": time_column,
        "split_strategy": "group_shuffle_split_feature_lab_fingerprint",
        "split_strategy_reason": "Identical six-feature plus two-lab fingerprints remain in one partition; year is excluded from model features.",
        "fingerprint_columns": fingerprint_columns,
        "fingerprint_group_count": split_info["group_count"],
        "split_fingerprint": split_info,
        "lab_features": args.lab_features,
        "label_leakage": {
            "proxy_rule": "HbA1c >= 6.5 OR blood_glucose_level >= 126",
            "adult_positive_labels": positive_count,
            "positive_labels_captured": captured_positives,
            "positive_label_capture_fraction": positive_capture,
            "negative_labels_flagged_by_proxy": false_positive_rows,
            "interpretation": label_leakage_interpretation(positive_capture),
        },
        "leakage_note": "A reviewed flag records operator review only; it does not prove leakage is absent. With-labs metrics are research comparisons and must not be interpreted as predictive-value evidence.",
        "results": all_results,
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
