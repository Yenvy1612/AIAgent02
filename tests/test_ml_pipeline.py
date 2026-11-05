from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml_training"))

from dataset_approval import (  # noqa: E402
    DatasetApprovalError, migrate_approval_v1_to_v2, validate_dataset_approval,
)
from evaluate import evaluate_artifact  # noqa: E402
from fixtures import FIXTURE_COLUMNS, make_fixture_dataset  # noqa: E402
from splitting import fingerprint_groups, resolve_split_columns, split_indices  # noqa: E402
import compare_features as compare_module  # noqa: E402
import train as train_module  # noqa: E402
from train import FEATURES, run_fixture_pipeline, subgroup_report  # noqa: E402


def _approved_v1_manifest(csv_path: Path) -> dict:
    return {
        "schema_version": 1,
        "status": "approved",
        "dataset_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "source_url": "https://example.org/fixture.csv",
        "rights_status": "approved",
        "rights_basis": "Locally generated test fixture; no third-party records.",
        "synthetic_only": True,
        "generation_method": "Deterministic test fixture generator.",
        "label_column": "diabetes",
        "label_definition": "Synthetic fixture label for pipeline verification.",
        "label_generation_method": "Alternating deterministic test labels.",
        "reviewer": "Fixture test",
        "reviewed_at": "2026-11-03",
        "review_note": "Test-only manifest; never used for a clinical artifact.",
        "known_limitations": ["Test-only fixture."],
    }


def _approved_v2_manifest(csv_path: Path) -> dict:
    return {
        "schema_version": 2,
        "status": "approved",
        "dataset_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "source_url": "https://example.org/fixture.csv",
        "rights_status": "approved",
        "rights_basis": "Test-only generated fixture; not third-party data.",
        "data_category": "public_research_dataset",
        "contains_real_patient_data": "unknown",
        "permitted_use": "academic_research_only",
        "known_limitations": ["Test-only fixture."],
        "label_column": "diabetes",
        "label_definition": "Fixture labels.",
        "label_generation_method": "Deterministic fixture rule.",
        "label_leakage_reviewed": True,
        "label_leakage_review_notes": "Reviewed as part of the schema migration test.",
        "reviewer": "Fixture test",
        "reviewed_at": "2026-11-03",
        "review_note": "Test-only manifest.",
    }


def _fast_fixture_estimators(y_train):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from xgboost import XGBClassifier

    labels = pd.Series(y_train).astype(int)
    positives = max(1, int((labels == 1).sum()))
    negatives = int((labels == 0).sum())
    return {
        "logistic_regression": LogisticRegression(max_iter=500, class_weight="balanced", random_state=42),
        "random_forest": RandomForestClassifier(
            n_estimators=8, min_samples_leaf=1, class_weight="balanced_subsample",
            random_state=42, n_jobs=1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=8, max_depth=2, eval_metric="logloss", random_state=42,
            scale_pos_weight=negatives / positives, n_jobs=1,
        ),
    }


def test_v1_approval_migration_preserves_pending_status():
    migrated = migrate_approval_v1_to_v2({
        "schema_version": 1, "status": "review_required", "synthetic_only": None,
        "known_limitations": ["Provenance unknown."],
    })
    assert migrated["schema_version"] == 2
    assert migrated["data_category"] == "public_research_dataset"
    assert migrated["contains_real_patient_data"] == "unknown"
    assert migrated["status"] == "review_required"
    assert migrated["known_limitations"] == ["Provenance unknown."]
    assert "synthetic_only" not in migrated


@pytest.mark.parametrize("version", [1, 2])
def test_validate_dataset_approval_accepts_both_reviewed_schema_versions(tmp_path: Path, version: int):
    source = tmp_path / "fixture.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = _approved_v1_manifest(source) if version == 1 else _approved_v2_manifest(source)
    manifest_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    approval, digest, _ = validate_dataset_approval(source, manifest_path, require_label_leakage_review=(version == 2))
    assert approval["schema_version"] == 2
    assert digest == hashlib.sha256(source.read_bytes()).hexdigest()


def test_user_authorized_real_candidate_allows_no_labs_but_blocks_with_labs():
    manifest_path = ROOT / "ml_training" / "dataset_approval.json"
    source = ROOT / "data" / "diabetes_dataset_with_notes.csv"
    approval, _, _ = validate_dataset_approval(source, manifest_path)
    assert approval["status"] == "approved"
    assert approval["permitted_use"] == "academic_research_only"
    assert approval["label_leakage_reviewed"] is False
    with pytest.raises(DatasetApprovalError, match="label-leakage assessment"):
        validate_dataset_approval(source, manifest_path, require_label_leakage_review=True)


def test_year_is_not_auto_selected_as_time_column():
    parser = argparse.ArgumentParser()
    assert resolve_split_columns(["year", "age", "diabetes"], None, None, parser) == (None, None)


def test_group_split_keeps_feature_lab_fingerprints_together():
    data = make_fixture_dataset()
    labels = data["diabetes"].astype(int)
    columns = FEATURES + ["hbA1c_level", "blood_glucose_level"]
    groups = fingerprint_groups(data, columns)
    splits = split_indices(data, labels, None, None, fingerprint_columns=columns)
    partition_groups = {name: set(groups.loc[ids]) for name, ids in splits.items()}
    assert not (partition_groups["train"] & partition_groups["validation"])
    assert not (partition_groups["train"] & partition_groups["test"])
    assert not (partition_groups["validation"] & partition_groups["test"])


def test_gender_subgroups_below_n_100_report_no_metric():
    sample = pd.DataFrame({
        "age": [40] * 120,
        "gender": ["Other"] * 18 + ["Female"] * 102,
    })
    labels = pd.Series(([0, 1] * 60), index=sample.index)
    result = subgroup_report(sample, labels, np.full(len(sample), 0.5), 0.5)
    assert result["gender"]["Other"] == {"n": 18, "status": "insufficient_n", "minimum_n": 100}
    assert "metrics" not in result["gender"]["Other"]


def test_label_leakage_interpretation_reports_measured_capture_without_inventing_100_percent():
    full_capture = compare_module.label_leakage_interpretation(1.0)
    partial_capture = compare_module.label_leakage_interpretation(0.25)
    unavailable = compare_module.label_leakage_interpretation(None)
    assert "captures 100%" in full_capture
    assert "does not reflect prospective predictive value" in full_capture
    assert "captures 25.0%" in partial_capture
    assert "captures 100%" not in partial_capture
    assert "cannot be measured" in unavailable


def test_production_candidate_factory_uses_all_reviewed_estimators_and_training_class_weight():
    candidates = train_module.research_candidate_estimators(pd.Series([0] * 6 + [1] * 2))
    assert set(candidates) == {"logistic_regression", "random_forest", "xgboost"}
    assert candidates["random_forest"].n_estimators == 350
    assert candidates["xgboost"].n_estimators == 350
    assert candidates["xgboost"].get_params()["scale_pos_weight"] == 3.0


def test_fixture_runs_through_training_split_threshold_and_artifact(tmp_path: Path):
    fixture = make_fixture_dataset()
    assert list(fixture.columns) == FIXTURE_COLUMNS
    fixture = pd.concat([fixture, fixture.iloc[[0]]], ignore_index=True)
    artifact = tmp_path / "risk_fixture.joblib"
    metadata = run_fixture_pipeline(fixture, artifact)
    assert artifact.is_file()
    assert artifact.with_suffix(".json").is_file()
    assert metadata["features"] == FEATURES
    assert metadata["usage"] == "research_only"
    assert metadata["clinical_validation"] is False
    assert metadata["exact_duplicate_rows_removed_across_all_original_columns"] == 1
    assert metadata["split_fingerprint"]["group_count"] > 100
    assert metadata["decision_threshold"] >= 0
    assert "confusion_matrix_tn_fp_fn_tp" in metadata["test_metrics"]

    csv_path = tmp_path / "fixture.csv"
    csv_path.write_bytes(fixture.to_csv(index=False).encode("utf-8"))
    report = evaluate_artifact(artifact, csv_path, tmp_path / "evaluation")
    assert report["status"] == "MEASURED"
    assert report["brier_score"] >= 0
    assert report["confusion_matrix"]
    assert report["roc_curve"]
    assert report["precision_recall_curve"]
    assert report["calibration_curve"]


def test_approved_cli_train_compare_and_evaluate_complete_on_generated_fixture(tmp_path: Path, monkeypatch):
    fixture = make_fixture_dataset(rows=240)
    fixture = pd.concat([fixture, fixture.iloc[[0]]], ignore_index=True)
    csv_path = tmp_path / "synthetic_fixture.csv"
    csv_path.write_bytes(fixture.to_csv(index=False).encode("utf-8"))

    # Approval is confined to this generated test fixture. The project manifest
    # and the unapproved research CSV are never changed or used for fitting.
    manifest = _approved_v2_manifest(csv_path)
    manifest.update({
        "data_category": "synthetic",
        "contains_real_patient_data": False,
        "generation_method": "Deterministic 17-column test fixture generator.",
        "review_note": "Temporary test-only manifest for a generated fixture; no project dataset approval.",
    })
    manifest_path = tmp_path / "fixture_approval.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(train_module, "research_candidate_estimators", _fast_fixture_estimators)
    monkeypatch.setattr(compare_module, "research_candidate_estimators", _fast_fixture_estimators)

    artifact_path = tmp_path / "risk_fixture.joblib"
    monkeypatch.setattr(sys, "argv", [
        "train.py", str(csv_path), "--approval-manifest", str(manifest_path),
        "--output", str(artifact_path), "--confirm-feature-contract",
    ])
    with contextlib.redirect_stdout(io.StringIO()):
        train_module.main()

    train_metadata = json.loads(artifact_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert artifact_path.is_file()
    assert train_metadata["data_category"] == "synthetic"
    assert train_metadata["usage"] == "research_only"
    assert train_metadata["clinical_validation"] is False
    assert train_metadata["exact_duplicate_rows_removed_across_all_original_columns"] == 1
    assert train_metadata["selected_candidate"] in {"logistic_regression", "random_forest", "xgboost"}
    assert train_metadata["recall_target"] == 0.90
    assert "split_fingerprint" in train_metadata
    assert "year_split_audit" in train_metadata

    evaluation = evaluate_artifact(artifact_path, csv_path, tmp_path / "evaluation", manifest_path)
    assert evaluation["status"] == "MEASURED"
    assert evaluation["confusion_matrix"]
    assert evaluation["roc_curve"]
    assert evaluation["precision_recall_curve"]
    assert evaluation["calibration_curve"]
    assert evaluation["brier_score"] >= 0

    comparison_path = tmp_path / "comparison.json"
    monkeypatch.setattr(sys, "argv", [
        "compare_features.py", str(csv_path), "--approval-manifest", str(manifest_path),
        "--output", str(comparison_path), "--confirm-feature-contract",
        "--lab-features", "hbA1c_level", "blood_glucose_level",
    ])
    with contextlib.redirect_stdout(io.StringIO()):
        compare_module.main()

    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["status"] == "MEASURED"
    assert comparison["shared_split_for_both_feature_sets"] is True
    assert comparison["split_fingerprint"]["sha256"] == train_metadata["split_fingerprint"]["sha256"]
    assert set(comparison["results"]) == {"risk_without_labs", "classifier_with_labs"}
    assert set(comparison["results"]["risk_without_labs"]["candidates"]) == {
        "logistic_regression", "random_forest", "xgboost",
    }
    leakage = comparison["label_leakage"]
    assert 0 <= leakage["positive_label_capture_fraction"] < 1
    assert f"{leakage['positive_label_capture_fraction']:.1%}" in leakage["interpretation"]
    assert "100%" not in leakage["interpretation"]
