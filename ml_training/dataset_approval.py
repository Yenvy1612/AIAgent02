from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path


class DatasetApprovalError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def migrate_approval_v1_to_v2(legacy: dict) -> dict:
    """Migrate v1 fields without changing the review decision or inventing approval."""
    if not isinstance(legacy, dict) or legacy.get("schema_version") != 1:
        raise DatasetApprovalError("Only schema_version 1 manifests can be migrated.")
    migrated = dict(legacy)
    synthetic_only = legacy.get("synthetic_only")
    migrated.update({
        "schema_version": 2,
        "data_category": "synthetic" if synthetic_only is True else "public_research_dataset",
        "contains_real_patient_data": False if synthetic_only is True else "unknown",
        "permitted_use": "academic_research_only",
        "known_limitations": list(legacy.get("known_limitations") or []),
        "legacy_migrated_from": 1,
    })
    migrated.pop("synthetic_only", None)
    return migrated


def normalize_approval_schema(approval: dict) -> dict:
    version = approval.get("schema_version") if isinstance(approval, dict) else None
    if version == 1:
        return migrate_approval_v1_to_v2(approval)
    if version == 2:
        return dict(approval)
    raise DatasetApprovalError("Approval manifest must use schema_version 1 or 2.")


def validate_dataset_approval(
    source: Path, manifest_path: Path, *, require_label_leakage_review: bool = False,
) -> tuple[dict, str, str]:
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise DatasetApprovalError(f"Approval manifest is unavailable: {manifest_path}") from exc
    try:
        raw_approval = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetApprovalError("Approval manifest must be valid UTF-8 JSON.") from exc
    approval = normalize_approval_schema(raw_approval)

    source_hash = sha256_file(source)
    approved_hash = str(approval.get("dataset_sha256", "")).lower()
    if approved_hash != source_hash:
        raise DatasetApprovalError("Dataset SHA-256 does not match the manifest entry.")
    if approval.get("status") != "approved":
        raise DatasetApprovalError("Dataset review status is not approved; training is refused.")

    if approval.get("data_category") not in {"synthetic", "public_research_dataset"}:
        raise DatasetApprovalError("data_category must be synthetic or public_research_dataset.")
    contains_real = approval.get("contains_real_patient_data")
    if contains_real not in {True, False, "unknown"}:
        raise DatasetApprovalError("contains_real_patient_data must be true, false, or 'unknown'.")
    if approval.get("data_category") == "synthetic" and contains_real is not False:
        raise DatasetApprovalError("Synthetic data must be reviewed as containing no real patient data.")
    if approval.get("permitted_use") != "academic_research_only":
        raise DatasetApprovalError("permitted_use must be academic_research_only.")
    if approval.get("data_category") == "public_research_dataset":
        if not isinstance(approval.get("rights_basis"), str) or not approval["rights_basis"].strip():
            raise DatasetApprovalError("Public research datasets require a documented rights_basis.")
        if approval.get("rights_status") != "approved":
            raise DatasetApprovalError("Public dataset usage rights are not approved in the manifest.")

    known_limitations = approval.get("known_limitations")
    if not isinstance(known_limitations, list) or any(not isinstance(item, str) or not item.strip() for item in known_limitations):
        raise DatasetApprovalError("known_limitations must be a list of non-empty strings.")
    required_text = ("source_url", "label_column", "label_definition", "label_generation_method", "reviewer", "reviewed_at")
    for field in required_text:
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            raise DatasetApprovalError(f"Approval manifest is missing required evidence: {field}.")
    if not approval["source_url"].startswith("https://"):
        raise DatasetApprovalError("source_url must be an HTTPS URL.")
    if not isinstance(approval.get("rights_basis"), str) or not approval["rights_basis"].strip():
        raise DatasetApprovalError("Approval manifest is missing required evidence: rights_basis.")
    if not approval.get("review_note", "").strip():
        raise DatasetApprovalError("Approved manifests require a review_note.")
    if require_label_leakage_review:
        if approval.get("label_leakage_reviewed") is not True:
            raise DatasetApprovalError("The manifest must record a reviewed label-leakage assessment before comparing lab features.")
        if not isinstance(approval.get("label_leakage_review_notes"), str) or not approval["label_leakage_review_notes"].strip():
            raise DatasetApprovalError("The manifest must include notes on possible label leakage before comparing lab features.")
    try:
        date.fromisoformat(approval["reviewed_at"])
    except ValueError as exc:
        raise DatasetApprovalError("reviewed_at must use YYYY-MM-DD format.") from exc

    return approval, source_hash, hashlib.sha256(manifest_bytes).hexdigest()
