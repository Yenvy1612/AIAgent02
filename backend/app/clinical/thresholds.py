"""Versioned educational thresholds for adults who are not pregnant.

The source metadata distinguishes Vietnamese guideline thresholds from
reference-only cutoffs. These rules are deterministic and do not depend on
retrieval. ADA is never treated as an approved or ingestible source here.
"""

from __future__ import annotations

THRESHOLD_VERSION = "diacare-adult-nonpregnant-v1"
POPULATION = "adult_non_pregnant"

_VN_SOURCE = {
    "source_code": "KB-01",
    "document_version": "2020-12-30",
    "page": 11,  # PDF page; printed page 9
    "section": "Phần 2, mục 1.1 — Chẩn đoán đái tháo đường",
    "review_status": "candidate",
    "license_status": "unknown",
    "source_url": "https://daithaoduong.kcb.vn/huong-dan-chan-doan-dieu-tri-dai-thao-duong-tip-2",
    "amended_by": "KB-01A",
}

_ADA_REFERENCE = {
    "source_code": "KB-06",
    "document_version": "reference_only",
    "page": None,
    "section": "ADA Standards of Care — reference cutoff only",
    "review_status": "reference_only",
    "license_status": "reference_only",
    "source_url": "https://professional.diabetes.org/standards-of-care",
}


def _threshold(
    threshold_id: str,
    value: float,
    unit: str,
    measurement_type: str,
    source: dict[str, object],
) -> dict[str, object]:
    return {
        "threshold_id": threshold_id,
        "value": value,
        "unit": unit,
        "measurement_type": measurement_type,
        "population": POPULATION,
        "threshold_version": THRESHOLD_VERSION,
        **source,
    }


THRESHOLDS: dict[str, tuple[dict[str, object], ...]] = {
    "hba1c": (
        _threshold("increased_risk", 5.7, "%", "hba1c", _ADA_REFERENCE),
        _threshold("diabetes_diagnostic", 6.5, "%", "hba1c", _VN_SOURCE),
    ),
    "fasting": (
        _threshold("increased_risk", 100, "mg/dL", "fasting", _ADA_REFERENCE),
        _threshold("diabetes_diagnostic", 126, "mg/dL", "fasting", _VN_SOURCE),
    ),
    "ogtt_2h": (
        _threshold("increased_risk", 140, "mg/dL", "ogtt_2h", _ADA_REFERENCE),
        _threshold("diabetes_diagnostic", 200, "mg/dL", "ogtt_2h", _VN_SOURCE),
    ),
    "random": (
        _threshold("diabetes_diagnostic_with_classic_symptoms", 200, "mg/dL", "random", _VN_SOURCE),
    ),
}


def relevant_thresholds(measurement_type: str, *, has_hba1c: bool = False) -> list[dict[str, object]]:
    """Return threshold metadata relevant to the supplied measurement."""
    result: list[dict[str, object]] = []
    if has_hba1c:
        result.extend(dict(row) for row in THRESHOLDS["hba1c"])
    if measurement_type in THRESHOLDS and measurement_type != "hba1c":
        result.extend(dict(row) for row in THRESHOLDS[measurement_type])
    return result
