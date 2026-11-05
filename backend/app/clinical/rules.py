from __future__ import annotations

import re
from typing import Any

from app.clinical.thresholds import POPULATION, THRESHOLD_VERSION, relevant_thresholds
from app.clinical.units import glucose_to_mg_dl


def _approved_matches(rule: dict[str, object], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_code = rule["source_code"]
    value = float(rule["value"])
    markers = {str(value), str(value).replace(".", ",")}
    marker_pattern = re.compile(r"(?<!\d)(?:" + "|".join(re.escape(x) for x in markers) + r")(?!\d)")
    for item in evidence:
        if (item.get("document_id") != source_code
                or item.get("review_status") != "approved"
                or item.get("license_status") != "approved"):
            continue
        text = str(item.get("excerpt", item.get("text", "")))
        if marker_pattern.search(text):
            return [item]
    return []


def _citation(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in (
        "citation_id", "document_id", "chunk_id", "title", "source_url", "page",
    ) if item.get(key) is not None}


def _rule_reference(rule: dict[str, object]) -> dict[str, Any]:
    code = str(rule["source_code"])
    title = {
        "KB-01": "Quyết định 5481/QĐ-BYT (2020), mục chẩn đoán",
        "KB-01A": "Quyết định 1353/QĐ-BYT (2021), văn bản sửa đổi",
        "KB-06": "ADA Standards of Care — tài liệu chỉ tham khảo",
    }.get(code, code)
    return {
        "reference_id": f"{code}:{rule['threshold_id']}",
        "source_code": code,
        "title": title,
        "source_url": rule.get("source_url"),
        "page": rule.get("page"),
        "version": rule.get("document_version"),
        "status": "reference_only",
    }


def interpret_labs(data: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    hba1c = data.get("hba1c_pct")
    glucose = data.get("glucose_value")
    unit = data.get("glucose_unit")
    measurement_type = data.get("measurement_type") or "unknown"
    fasting_confirmed = data.get("fasting_confirmed")
    classic_symptoms = bool(data.get("classic_symptoms", False))

    if data.get("hba1c_unit_unsupported") or data.get("hba1c_unit") == "mmol/mol":
        return {
            "status": "UNSUPPORTED_UNIT", "result": "hba1c_mmol_mol_unsupported",
            "findings": [], "diagnosis": False, "citations": [], "reference_only": [],
            "message": "Bản demo chỉ diễn giải HbA1c theo %. HbA1c mmol/mol hiện chưa được hỗ trợ.",
        }
    if hba1c is None and glucose is None:
        return {"status": "INVALID_INPUT", "message": "Cần cung cấp HbA1c hoặc glucose."}
    if glucose is not None and unit not in {"mg/dL", "mmol/L"}:
        return {
            "status": "NEED_CLARIFICATION", "result": "unit_required",
            "message": "Bạn cho biết glucose được đo bằng mg/dL hay mmol/L, và đo lúc đói, ngẫu nhiên hay sau nghiệm pháp 2 giờ?",
            "original_value": glucose, "original_unit": None, "normalized_value_mg_dl": None,
            "measurement_type": measurement_type, "findings": [], "diagnosis": False,
            "citations": [],
        }

    normalized = glucose_to_mg_dl(float(glucose), str(unit)) if glucose is not None else None
    if glucose is not None and measurement_type not in {"fasting", "ogtt_2h", "random"} and hba1c is None:
        return {
            "status": "NEED_CLARIFICATION", "result": "measurement_type_required",
            "original_value": glucose, "original_unit": unit,
            "normalized_value_mg_dl": round(normalized, 2),
            "measurement_type": measurement_type, "findings": [], "diagnosis": False,
            "citations": [],
            "message": "Bạn cho biết phép đo glucose là lúc đói, ngẫu nhiên hay sau nghiệm pháp 2 giờ? Mình chưa diễn giải ngưỡng khi chưa rõ loại phép đo.",
        }

    rules = relevant_thresholds(measurement_type, has_hba1c=hba1c is not None)
    supplied_evidence = evidence or []
    matched: dict[str, dict[str, Any]] = {}
    rule_source: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    for rule in rules:
        matches = _approved_matches(rule, supplied_evidence)
        if matches:
            item = matches[0]
            if item.get("chunk_id"):
                matched[str(item["chunk_id"])] = item
            state = "supported"
        else:
            references.append(_rule_reference(rule))
            state = "reference_only"
        rule_source.append({
            "source_code": rule["source_code"],
            "version": rule["document_version"],
            "page": rule["page"],
            "section": rule["section"],
            "measurement_type": rule["measurement_type"],
            "population": POPULATION,
            "threshold_version": THRESHOLD_VERSION,
            "threshold_id": rule["threshold_id"],
            "value": rule["value"],
            "unit": rule["unit"],
            "amended_by": rule.get("amended_by"),
            "evidence_status": state,
        })

    findings: list[str] = []
    if hba1c is not None:
        if hba1c >= 6.5:
            findings.append("hba1c_at_or_above_diabetes_diagnostic_threshold")
        elif hba1c >= 5.7:
            findings.append("hba1c_in_increased_risk_range_reference")
        else:
            findings.append("hba1c_below_increased_risk_range_cutoff")

    if glucose is not None:
        if measurement_type == "fasting":
            if fasting_confirmed is False:
                findings.append("fasting_not_confirmed_measurement_type_conflict")
            elif normalized >= 126:
                findings.append("fasting_glucose_at_or_above_diabetes_diagnostic_threshold")
            elif normalized >= 100:
                findings.append("fasting_glucose_in_increased_risk_range_reference")
            else:
                findings.append("fasting_glucose_below_reference_cutoff")
        elif measurement_type == "ogtt_2h":
            if normalized >= 200:
                findings.append("ogtt_2h_at_or_above_diabetes_diagnostic_threshold")
            elif normalized >= 140:
                findings.append("ogtt_2h_in_increased_risk_range_reference")
            else:
                findings.append("ogtt_2h_below_reference_cutoff")
        elif measurement_type == "random":
            if normalized >= 200 and classic_symptoms:
                findings.append("random_glucose_with_classic_symptoms_at_diagnostic_threshold")
            elif normalized >= 200:
                findings.append("random_glucose_high_confirmation_required")
            else:
                findings.append("random_glucose_not_interpreted_as_diagnostic")

    diagnostic_range = any("at_or_above_diabetes_diagnostic_threshold" in f or "at_diagnostic_threshold" in f for f in findings)
    random_with_symptoms = "random_glucose_with_classic_symptoms_at_diagnostic_threshold" in findings
    high_random_without_symptoms = "random_glucose_high_confirmation_required" in findings
    clinical_review_required = diagnostic_range or high_random_without_symptoms
    needs_confirmation = (diagnostic_range or high_random_without_symptoms) and not random_with_symptoms
    citations = [_citation(item) for item in matched.values()]
    return {
        "status": "OK",
        "result": "threshold_range_requires_clinical_review" if clinical_review_required else "no_diagnostic_conclusion",
        "findings": findings,
        "hba1c_pct": hba1c,
        "original_value": glucose,
        "original_unit": unit,
        "normalized_value_mg_dl": round(normalized, 2) if normalized is not None else None,
        "measurement_type": measurement_type,
        "population": POPULATION,
        "clinical_review_required": bool(clinical_review_required),
        "confirmation_required": bool(needs_confirmation),
        "diagnosis": False,
        "message": (
            "Giá trị nằm ở hoặc trên một ngưỡng tham khảo cần được nhân viên y tế đánh giá. "
            "Tùy triệu chứng và bối cảnh, người chuyên môn quyết định có cần xét nghiệm xác nhận hay không. Đây không phải chẩn đoán."
            if clinical_review_required else
            "Đây chỉ là diễn giải ngưỡng tham khảo; kết quả này không đủ để xác nhận hay loại trừ bệnh. Đây không phải chẩn đoán. Hãy trao đổi với nhân viên y tế."
        ),
        "rule_source": rule_source,
        "threshold_version": THRESHOLD_VERSION,
        "evidence_status": "supported" if citations else "reference_only",
        "citations": citations,
        "reference_only": references,
    }
