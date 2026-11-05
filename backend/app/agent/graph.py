from __future__ import annotations

import re
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.fusion import structured_fusion
from app.agent.guidance import INSUFFICIENT_EVIDENCE_MESSAGE, classify_guidance, guidance_message
from app.agent.tools import (
    calculate_bmi, classify_lab, predict_risk, profile_features, screen_risk, should_screen_risk,
    search_kb, search_web, tool_get_history,
)
from app.rag.citations import validate_citations
from app.rag.scope import is_in_kb_scope
from app.rag.web_search import WEB_UNVERIFIED_NOTICE, sanitize_web_query, web_search_enabled
from app.llm.composer import compose_answer
from app.llm.config import get_config
from app.safety.gate import (
    EMERGENCY_MESSAGE, contains_medication_dose, evaluate_safety, medication_request, normalize_vi,
)
from app.safety.keyword_rules import mentions_treatment_regimen, redact_medication_sentences

DOSE_HEAVY_TOPICS = {"medication", "hospital", "complications"}
MIN_REDACTED_CHARS = 200
MIN_REDACTED_SHARE = 0.4
REDACTION_NOTICE = "Lưu ý: các câu nhắc đến thuốc hoặc liều dùng đã được lược bỏ khỏi đoạn trích."
FALLBACK_SOURCE_NOTICE = "Bạn xem thêm trong phần nguồn bên dưới."
FALLBACK_EXCERPT_MAX_CHARS = 400
_FALLBACK_SENTENCE_END = re.compile(r"[.!?](?:[\"'”’)\]]*)?(?=\s|$)")
_SCORE_TABLE_HINT = re.compile(r"\b(?:diem|score)\b")
_HEADING_FRAGMENT = re.compile(r"(?:\d+(?:\.\d+)*|[A-Z])[.)]?", re.IGNORECASE)
_LIST_MARKER_FRAGMENT = re.compile(r":\s*[a-z]\.$", re.IGNORECASE)

MEDICATION_REFUSAL_MESSAGE = (
    "Mình không thể tư vấn tăng, giảm, ngừng hoặc thay liều insulin/thuốc. "
    "Hãy liên hệ bác sĩ hoặc dược sĩ đang theo dõi để được hướng dẫn phù hợp; "
    "nếu có triệu chứng cấp cứu, gọi 115."
)
WOUND_CARE_REFUSAL_MESSAGE = (
    "Mình không thể hướng dẫn tự xử trí vết loét hoặc vết thương ở bàn chân. "
    "Hãy đến cơ sở y tế hoặc liên hệ nhân viên y tế sớm để được khám; nếu có triệu chứng cấp cứu, gọi 115."
)
SAFETY_UNCERTAIN_MESSAGE = (
    "Mình chưa thể đánh giá tình huống này một cách tin cậy. Nếu bạn hoặc người bên cạnh đang bất tỉnh, "
    "co giật, lú lẫn, khó thở, đau ngực hoặc không thể nuốt, hãy gọi 115 ngay hoặc nhờ người bên cạnh gọi. "
    "Không tự lái xe và không tự thay đổi liều thuốc. Nếu không có dấu hiệu cấp cứu, hãy liên hệ nhân viên y tế để được đánh giá."
)


def _parse_measurement(message: str) -> dict[str, Any]:
    normalized = normalize_vi(message)
    result: dict[str, Any] = {"hba1c_pct": None, "hba1c_unit_unsupported": False, "glucose_value": None, "glucose_unit": None, "measurement_type": "unknown"}
    hba1c = re.search(r"(?:hba1c|a1c)\D{0,12}(\d{1,2}(?:[.,]\d+)?)\s*(mmol\s*/?\s*mol|%)?", normalized)
    if hba1c:
        value = float(hba1c.group(1).replace(",", "."))
        if (hba1c.group(2) and hba1c.group(2).startswith("mmol")) or value > 30:
            result["hba1c_unit_unsupported"] = True
        else:
            result["hba1c_pct"] = value
    glucose = re.search(r"(?:glucose|duong huyet|duong mau)\D{0,24}(\d{1,4}(?:[.,]\d+)?)\s*(mg\s*/?\s*dl|mmol\s*/?\s*l)?", normalized)
    if glucose:
        result["glucose_value"] = float(glucose.group(1).replace(",", "."))
        unit = (glucose.group(2) or "").replace(" ", "")
        if unit in {"mg/dl", "mgdl"}:
            result["glucose_unit"] = "mg/dL"
        elif unit in {"mmol/l", "mmoll"}:
            result["glucose_unit"] = "mmol/L"
    if any(word in normalized for word in ("luc doi", "fasting", "nhin an")):
        result["measurement_type"] = "fasting"
        result["fasting_confirmed"] = True
    elif "nghiem phap" in normalized or "ogtt" in normalized or "sau 2 gio" in normalized:
        result["measurement_type"] = "ogtt_2h"
    elif "ngau nhien" in normalized or "random" in normalized:
        result["measurement_type"] = "random"
    result["classic_symptoms"] = any(term in normalized for term in ("khat nhieu", "di tieu nhieu", "sut can khong ro ly do"))
    return result


def _parse_bmi(message: str) -> tuple[float | None, float | None]:
    normalized = normalize_vi(message)
    pattern = re.search(r"(\d{2,3}(?:[.,]\d+)?)\s*kg\D{0,20}(\d{2,3}(?:[.,]\d+)?)\s*cm", normalized)
    if not pattern:
        return None, None
    return float(pattern.group(1).replace(",", ".")), float(pattern.group(2).replace(",", "."))


def _route_message(message: str) -> tuple[str, list[str]]:
    text = normalize_vi(message)
    measurement = _parse_measurement(message)
    if should_screen_risk(message):
        return measurement, ["screen_risk"]
    weight, height = _parse_bmi(message)
    routes: list[str] = []
    if measurement["hba1c_pct"] is not None or measurement["hba1c_unit_unsupported"] or measurement["glucose_value"] is not None:
        needs_measurement_clarification = (
            measurement["glucose_value"] is not None
            and measurement["measurement_type"] not in {"fasting", "random", "ogtt_2h"}
            and measurement["hba1c_pct"] is None
            and not measurement["hba1c_unit_unsupported"]
        )
        routes.extend(["classify_lab"] if needs_measurement_clarification else ["search_kb", "classify_lab"])
    if any(term in text for term in ("lich su", "thang truoc", "cac lan do", "chi so gan day", "history", "tom tat ho so", "tom tat cho bac si")):
        routes.append("get_history")
    if "bmi" in text or (weight is not None and height is not None):
        routes.append("calculate_bmi")
    if any(term in text for term in ("theo mo hinh", "danh gia ho so", "predict risk", "phan loai nghien cuu")):
        routes.append("predict_risk")
    explanation_requested = any(term in text for term in (
        "shap", "yeu to anh huong", "yeu to lien quan", "dong gop dac trung", "feature importance",
    ))
    if explanation_requested:
        routes.append("predict_risk")
        routes.append("search_kb")
    if not routes:
        routes.append("search_kb")
    return measurement, list(dict.fromkeys(routes))


def _safety_node(state: AgentState) -> dict[str, Any]:
    parsed = _parse_measurement(state["message"])
    safety = evaluate_safety(state["message"], parsed.get("glucose_value"), parsed.get("glucose_unit"))
    return {"safety": safety, "parsed": parsed, "trace": [{"step": "safety_gate", "status": safety["level"]}]}


def _safety_route(state: AgentState) -> str:
    if state["safety"]["level"] == "EMERGENCY":
        return "emergency"
    if state["safety"]["level"] == "UNKNOWN":
        return "uncertain"
    if state["safety"]["level"] == "CLINICAL_REVIEW":
        return "refusal"
    if state["safety"]["level"] == "UNIT_AMBIGUOUS":
        return "unit_clarification"
    if classify_guidance(state["message"]):
        return "guidance"
    return "continue"


def _emergency_node(state: AgentState) -> dict[str, Any]:
    return {
        **structured_fusion(safety_level="EMERGENCY", profile_type=None),
        "answer": EMERGENCY_MESSAGE,
        "status": "EMERGENCY",
        "tool_calls": [], "evidence": [], "citations": [],
        "trace": state.get("trace", []) + [{"step": "agent_bypass", "status": "EMERGENCY_RESPONSE_SENT"}],
    }


def _guidance_node(state: AgentState) -> dict[str, Any]:
    kind = classify_guidance(state["message"]) or "usage"
    return {
        **structured_fusion(
            safety_level=state["safety"]["level"],
            profile_type="synthetic" if state.get("profile_id") else None,
        ),
        "answer": guidance_message(kind, has_profile=bool(state.get("profile_id"))),
        "status": "NEED_CLARIFICATION" if kind == "lab_input" else "OK",
        "answer_mode": "deterministic",
        "tool_calls": [], "evidence": [], "citations": [],
        "trace": state.get("trace", []) + [{"step": "guidance", "status": kind.upper()}],
    }


def _safety_uncertain_node(state: AgentState) -> dict[str, Any]:
    return {
        "answer": SAFETY_UNCERTAIN_MESSAGE,
        "status": "SAFETY_UNCERTAIN", "tool_calls": [], "evidence": [], "citations": [],
        "trace": state.get("trace", []) + [{"step": "agent_bypass", "status": "SAFETY_CLASSIFIER_UNAVAILABLE"}],
    }


def _refusal_node(state: AgentState) -> dict[str, Any]:
    wound_care = state.get("safety", {}).get("wound_care_request")
    return {
        "answer": WOUND_CARE_REFUSAL_MESSAGE if wound_care else MEDICATION_REFUSAL_MESSAGE,
        "status": "CLINICAL_REVIEW", "tool_calls": [], "evidence": [], "citations": [],
        "trace": state.get("trace", []) + [{"step": "medication_boundary", "status": "REFUSED_AND_REFERRED"}],
    }


def _unit_clarification_node(state: AgentState) -> dict[str, Any]:
    parsed = state.get("parsed", {})
    value = parsed.get("glucose_value")
    extra = (
        f" Nếu {value:g} là mg/dL thì đây là mức rất thấp; hãy xác nhận đơn vị ngay."
        if value is not None and value < 54 else ""
    )
    answer = (
        "Bạn cho biết đơn vị glucose là mg/dL hay mmol/L, đồng thời phép đo là lúc đói, ngẫu nhiên hay sau nghiệm pháp 2 giờ?"
        + extra
        + " Nếu không thể xác nhận đơn vị ngay, hoặc có bất tỉnh, co giật, lú lẫn hay khó thở, hãy nhờ người bên cạnh hỗ trợ và gọi 115."
    )
    return {
        "answer": answer, "status": "NEED_CLARIFICATION", "tool_calls": [],
        "evidence": [], "citations": [],
        "trace": state.get("trace", []) + [{"step": "unit_safety", "status": "CLARIFICATION_REQUIRED"}],
    }


def _route_node(state: AgentState) -> dict[str, Any]:
    parsed, call_names = _route_message(state["message"])
    if parsed.get("hba1c_unit_unsupported"):
        call_names = ["classify_lab"]
    elif parsed.get("glucose_value") is not None and parsed.get("glucose_unit") is None:
        call_names = []
    if "predict_risk" in call_names and "get_history" not in call_names:
        call_names.insert(0, "get_history")
    calls = [{"name": name} for name in call_names[:5]]
    intent = "+".join(call_names[:5])
    return {"parsed": parsed, "calls": calls, "intent": intent,
            "trace": state.get("trace", []) + [{"step": "intent_router", "status": intent or "NO_TOOL"}]}


def _vietnamese_findings(findings: list[str]) -> list[str]:
    labels = {
        "hba1c_at_or_above_diabetes_diagnostic_threshold": "HbA1c ở hoặc trên ngưỡng xét nghiệm cần được đánh giá lâm sàng",
        "hba1c_in_increased_risk_range_reference": "HbA1c trong khoảng tăng nguy cơ tham khảo",
        "hba1c_below_increased_risk_range_cutoff": "HbA1c thấp hơn khoảng tăng nguy cơ tham khảo",
        "fasting_glucose_at_or_above_diabetes_diagnostic_threshold": "glucose lúc đói ở hoặc trên ngưỡng xét nghiệm cần được đánh giá lâm sàng",
        "fasting_glucose_in_increased_risk_range_reference": "glucose lúc đói trong khoảng tăng nguy cơ tham khảo",
        "fasting_glucose_below_reference_cutoff": "glucose lúc đói thấp hơn khoảng tham khảo tăng nguy cơ",
        "fasting_not_confirmed_measurement_type_conflict": "thông tin nhịn đói chưa được xác nhận",
        "ogtt_2h_at_or_above_diabetes_diagnostic_threshold": "glucose sau nghiệm pháp 2 giờ ở hoặc trên ngưỡng xét nghiệm cần được đánh giá lâm sàng",
        "ogtt_2h_in_increased_risk_range_reference": "glucose sau nghiệm pháp 2 giờ trong khoảng tăng nguy cơ tham khảo",
        "ogtt_2h_below_reference_cutoff": "glucose sau nghiệm pháp 2 giờ thấp hơn khoảng tham khảo tăng nguy cơ",
        "random_glucose_with_classic_symptoms_at_diagnostic_threshold": "glucose ngẫu nhiên cùng triệu chứng cần được nhân viên y tế đánh giá ngay",
        "random_glucose_high_confirmation_required": "glucose ngẫu nhiên cao; cần nhân viên y tế đánh giá và xác nhận",
        "random_glucose_not_interpreted_as_diagnostic": "glucose ngẫu nhiên không được dùng riêng lẻ để kết luận",
        "measurement_type_needed_for_interpretation": "cần biết đây là phép đo lúc đói, ngẫu nhiên hay sau nghiệm pháp 2 giờ",
    }
    return [labels.get(item, item) for item in findings]


def _web_fallback_query(state: AgentState, results: dict[str, Any]) -> str | None:
    """Return a filtered query only for a general diabetes question the approved KB cannot answer."""
    message = state["message"]
    parsed = state.get("parsed", {})
    if (
        not web_search_enabled()
        or set(results) != {"search_kb"}
        or results["search_kb"].get("status") != "INSUFFICIENT_EVIDENCE"
        or state.get("safety", {}).get("level") != "NORMAL"
        or state.get("profile_id")
        or medication_request(message)
        or not is_in_kb_scope(message)
        or parsed.get("glucose_value") is not None
        or parsed.get("hba1c_pct") is not None
        or any(value is not None for value in _parse_bmi(message))
    ):
        return None
    return sanitize_web_query(message)


def _execute_tools_node(state: AgentState) -> dict[str, Any]:
    db = state["db"]
    message = state["message"]
    profile_id = state.get("profile_id")
    parsed = state.get("parsed", {})
    results: dict[str, Any] = {}
    calls: list[dict[str, Any]] = []
    trace = list(state.get("trace", []))
    for call in state.get("calls", [])[:5]:
        name = call["name"]
        args: dict[str, Any] = {}
        try:
            if name == "screen_risk":
                args = {"message": message}
                result = screen_risk(message)
            elif name == "classify_lab":
                args = dict(parsed)
                if parsed.get("hba1c_unit_unsupported"):
                    result = {
                        "status": "NEED_CLARIFICATION",
                        "message": "MVP chỉ diễn giải HbA1c nhập theo %. Nếu phiếu xét nghiệm ghi mmol/mol, hãy hỏi nhân viên y tế hoặc dùng công cụ chuyển đổi đã được xác minh.",
                    }
                else:
                    result = classify_lab(args, evidence=results.get("search_kb", {}).get("evidence", []))
            elif name == "search_kb":
                is_lab_query = any(value is not None for value in (parsed.get("hba1c_pct"), parsed.get("glucose_value")))
                args = {"query": message, "topic": "diagnosis" if is_lab_query else None, "top_k": 5}
                result = search_kb(**args)
            elif name == "get_history":
                args = {"demo_profile_id": profile_id}
                result = tool_get_history(db, profile_id) if profile_id else {"status": "PROFILE_REQUIRED"}
            elif name == "calculate_bmi":
                weight, height = _parse_bmi(message)
                if weight is None and profile_id:
                    profile, _ = profile_features(db, profile_id)
                    if profile:
                        weight, height = profile["weight_kg"], profile["height_cm"]
                args = {"weight_kg": weight, "height_cm": height}
                result = calculate_bmi(weight, height) if weight and height else {"status": "PROFILE_REQUIRED", "message": "Cung cấp cân nặng kg và chiều cao cm, hoặc chọn hồ sơ mô phỏng."}
            elif name == "predict_risk":
                profile, features = profile_features(db, profile_id) if profile_id else (None, None)
                include_explanation = any(term in normalize_vi(message) for term in (
                    "shap", "yeu to anh huong", "yeu to lien quan", "dong gop dac trung", "feature importance",
                ))
                args = {**(features or {}), "include_explanation": include_explanation}
                result = predict_risk(features, include_explanation) if features else {"status": "PROFILE_REQUIRED", "usage": "research_only"}
            else:
                result = {"status": "UNKNOWN_TOOL"}
            results[name] = result
            calls.append({"tool": name, "status": result.get("status", "OK"), "arguments": args})
            tool_trace = {"step": f"tool:{name}", "status": result.get("status", "OK")}
            if result.get("retrieval_mode"):
                tool_trace["retrieval_mode"] = result["retrieval_mode"]
            if result.get("degraded_reason"):
                tool_trace["degraded_reason"] = result["degraded_reason"]
            trace.append(tool_trace)
        except Exception as exc:
            results[name] = {"status": "TOOL_ERROR", "message": type(exc).__name__}
            calls.append({"tool": name, "status": "TOOL_ERROR", "arguments": args})
            trace.append({"step": f"tool:{name}", "status": "TOOL_ERROR"})
    web_query = _web_fallback_query(state, results)
    if web_query:
        try:
            web_result = search_web(web_query)
        except Exception as exc:
            web_result = {"status": "UNAVAILABLE", "reason": type(exc).__name__}
        results["search_web"] = web_result
        calls.append({"tool": "search_web", "status": web_result["status"], "arguments": {"query": web_query}})
        trace.append({"step": "tool:search_web", "status": web_result["status"], "reason": web_result.get("reason")})
    return {"results": results, "tool_calls": calls, "trace": trace}


def _evidence_without_doses(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep general text from guideline excerpts so one dose mention does not trigger a refusal.

    Treatment chapters are dropped whole, as is any excerpt left mostly empty, because the remaining
    fragments could read as treatment advice. The output guard still checks the final answer.
    """
    kept = []
    for item in items:
        excerpt = item.get("excerpt", "")
        if not contains_medication_dose(excerpt) and not mentions_treatment_regimen(excerpt):
            kept.append(item)
        elif item.get("topic") not in DOSE_HEAVY_TOPICS:
            redacted = redact_medication_sentences(excerpt)
            if len(redacted) >= max(MIN_REDACTED_CHARS, len(excerpt) * MIN_REDACTED_SHARE):
                kept.append({**item, "excerpt": redacted, "excerpt_redacted": True})
    return kept


def _is_score_table(excerpt: str) -> bool:
    lines = [line.strip() for line in excerpt.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    if sum("|" in line for line in lines) >= 2:
        return True
    return bool(_SCORE_TABLE_HINT.search(normalize_vi(excerpt))) and sum(
        bool(re.search(r"\d", line)) for line in lines
    ) >= 2


def _best_fallback_excerpt(items: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    """Choose up to two complete prose sentences, preserving their excerpt text verbatim."""
    for item in items:
        excerpt = str(item.get("excerpt", ""))
        if not excerpt.strip() or _is_score_table(excerpt):
            continue
        sentence_count = 0
        selected_start: int | None = None
        selected_end: int | None = None
        segment_start = 0
        for boundary in _FALLBACK_SENTENCE_END.finditer(excerpt):
            segment = excerpt[segment_start:boundary.end()]
            leading_space = len(segment) - len(segment.lstrip())
            sentence = segment.strip()
            sentence_start = segment_start + leading_space
            segment_start = boundary.end()
            if (
                not sentence
                or _HEADING_FRAGMENT.fullmatch(sentence)
                or any(_HEADING_FRAGMENT.fullmatch(line.strip()) for line in sentence.splitlines()[1:])
                or _LIST_MARKER_FRAGMENT.search(sentence)
            ):
                continue
            candidate_start = sentence_start if selected_start is None else selected_start
            candidate = excerpt[candidate_start:boundary.end()].strip()
            if len(candidate) > FALLBACK_EXCERPT_MAX_CHARS:
                break
            if selected_start is None:
                selected_start = sentence_start
            selected_end = boundary.end()
            sentence_count += 1
            if sentence_count == 2:
                break
        if selected_start is not None and selected_end is not None:
            return item, excerpt[selected_start:selected_end].strip()
    return None, None


def _compose_node(state: AgentState) -> dict[str, Any]:
    results = state.get("results", {})
    if "screen_risk" in results:
        screening = results["screen_risk"]
        answer = screening.get("answer", INSUFFICIENT_EVIDENCE_MESSAGE)
        evidence = screening.get("evidence", [])
        status = screening.get("status", "OK")
        return {
            "answer": answer, "deterministic_answer": answer,
            "fact_parts": [answer], "note_parts": [], "answer_mode": "deterministic",
            "evidence": evidence, "citations": screening.get("citations", []),
            "reference_only": [], "web_sources": [], "status": status,
            "trace": state.get("trace", []) + [{"step": "fusion", "status": status}],
            **structured_fusion(
                evidence=evidence, safety_level=state.get("safety", {}).get("level", "UNKNOWN"),
                profile_type="synthetic" if state.get("profile_id") else None,
            ),
        }
    parts: list[str] = []
    evidence: list[dict[str, Any]] = []
    reference_only: list[dict[str, Any]] = []
    rule_citations: list[dict[str, Any]] = []
    web_sources: list[dict[str, Any]] = []
    status = "OK"
    if medication_request(state["message"]):
        return _refusal_node(state)
    if "classify_lab" in results:
        lab = results["classify_lab"]
        if lab.get("status") == "NEED_CLARIFICATION":
            if lab.get("normalized_value_mg_dl") is not None:
                parts.append(
                    f"Glucose nhập: {lab['original_value']} {lab.get('original_unit')}; "
                    f"quy đổi số học tham khảo: {lab['normalized_value_mg_dl']} mg/dL."
                )
            parts.append(lab["message"])
            status = "NEED_CLARIFICATION"
        elif lab.get("status") == "INSUFFICIENT_EVIDENCE":
            if lab.get("normalized_value_mg_dl") is not None:
                parts.append(
                    f"Glucose nhập: {lab['original_value']} {lab.get('original_unit')}; "
                    f"quy đổi số học tham khảo: {lab['normalized_value_mg_dl']} mg/dL."
                )
            parts.append(lab["message"])
            status = "DEGRADED"
        elif lab.get("status") == "OK":
            translated_findings = _vietnamese_findings(lab.get("findings", []))
            if lab.get("hba1c_pct") is not None:
                hba1c_findings = [text for code, text in zip(lab.get("findings", []), translated_findings) if code.startswith("hba1c_")]
                parts.append(f"HbA1c {lab['hba1c_pct']}%: {', '.join(hba1c_findings) or 'đã nhận giá trị'}.")
            if lab.get("original_value") is not None:
                normalized = lab.get("normalized_value_mg_dl")
                glucose_findings = [text for code, text in zip(lab.get("findings", []), translated_findings) if not code.startswith("hba1c_")]
                parts.append(f"Glucose nhập: {lab['original_value']} {lab.get('original_unit')}; quy đổi tham khảo: {normalized} mg/dL. {', '.join(glucose_findings)}.")
                if "measurement_type_needed_for_interpretation" in lab.get("findings", []):
                    parts.append("Bạn đo lúc đói, ngẫu nhiên, hay sau nghiệm pháp 2 giờ?")
            parts.append(lab["message"])
            parts.append(f"Quy tắc {lab.get('threshold_version', 'version chưa rõ')} áp dụng cho người trưởng thành không mang thai; kết quả không phải chẩn đoán.")
            reference_only.extend(lab.get("reference_only", []))
            rule_citations.extend(lab.get("citations", []))
            status = "OK"
        else:
            parts.append(lab.get("message", "Không thể diễn giải dữ liệu đã nhập."))
            status = "DEGRADED"
    if "calculate_bmi" in results:
        bmi = results["calculate_bmi"]
        if bmi.get("status") == "OK":
            parts.append(f"BMI tính được là {bmi['bmi']} {bmi['unit']}. Đây là phép tính chỉ số, không phải chẩn đoán.")
        else:
            parts.append(bmi.get("message", "Chưa đủ dữ liệu để tính BMI."))
    if "get_history" in results:
        history = results["get_history"]
        if history.get("status") == "OK":
            values = history["readings"]
            recent = values[-1] if values else None
            if recent and any(term in normalize_vi(state["message"]) for term in ("tom tat ho so", "tom tat cho bac si")):
                mg_values = [row["glucose_mg_dl"] for row in values]
                dates = [row["measured_at"][:10] for row in values]
                profile = history["profile"]
                parts.append(
                    f"Tóm tắt hồ sơ tổng hợp {profile['profile_code']}: {profile['age']} tuổi; "
                    f"{len(values)} phép đo glucose từ {dates[0]} đến {dates[-1]}; "
                    f"giá trị quy đổi dao động {min(mg_values):.0f}–{max(mg_values):.0f} mg/dL. "
                    f"Lần gần nhất: {recent['original_value']} {recent['original_unit']} ({recent['measurement_type']})."
                )
            elif recent:
                parts.append(f"{history['profile']['display_name']} có {len(values)} phép đo glucose tổng hợp. Lần gần nhất: {recent['original_value']} {recent['original_unit']} ({recent['measurement_type']}).")
            else:
                parts.append("Hồ sơ tổng hợp chưa có phép đo glucose.")
            parts.append("Dữ liệu lịch sử trong demo được tạo tổng hợp, không đại diện hồ sơ thật.")
        else:
            parts.append("Hãy chọn một hồ sơ mô phỏng để xem lịch sử chỉ số.")
            status = "DEGRADED"
    if "predict_risk" in results:
        risk = results["predict_risk"]
        if risk.get("status") == "OK":
            parts.append(f"Kết quả mô hình nghiên cứu: score {risk['model_score']:.3f}, lớp {risk['predicted_class']}, phiên bản {risk['model_version']}. Mô hình phân loại nhãn hiện mắc trong tập nghiên cứu, không dự báo tương lai và chưa được xác thực lâm sàng.")
            explanation = risk.get("explanation")
            if explanation:
                if explanation.get("status") == "OK":
                    summary = "; ".join(f"{item['feature']}: {item['contribution']:+.3f}" for item in explanation.get("contributions", [])[:5])
                    parts.append(f"SHAP contributions (model output only): {summary}. Contributions do not show causation.")
                else:
                    parts.append("SHAP giải thích hiện chưa sẵn sàng; cần cài SHAP cùng với artifact mô hình.")
        elif risk.get("status") == "PROFILE_REQUIRED":
            parts.append("Hãy chọn một hồ sơ mô phỏng để xem kết quả mô hình nghiên cứu.")
            status = "DEGRADED"
        else:
            parts.append("Mô hình nghiên cứu hiện chưa sẵn sàng: chưa có dữ liệu CSV được rà soát và mô hình huấn luyện. Không tạo score thay thế.")
            status = "DEGRADED"
    if "search_kb" in results:
        search = results["search_kb"]
        evidence = _evidence_without_doses(search.get("evidence", []))
        if evidence:
            for item in evidence[:5]:
                parts.append(item["excerpt"][:700])
            for item in evidence:
                amended_by = item.get("amended_by") or []
                if item.get("amended") and amended_by:
                    names = ", ".join(
                        "Quyết định 1353/QĐ-BYT" if code == "KB-01A" else str(code)
                        for code in amended_by
                    )
                    parts.append(
                        f"Lưu ý: đoạn trích thuộc phần đã được sửa đổi bởi {names}; "
                        "cần đối chiếu văn bản sửa đổi trước khi áp dụng."
                    )
            if any(item.get("excerpt_redacted") for item in evidence):
                parts.append(REDACTION_NOTICE)
        elif results.get("search_web", {}).get("status") == "OK":
            # Web content stays out of evidence and citations, which mean "approved" everywhere else.
            web = results["search_web"]
            parts.extend([WEB_UNVERIFIED_NOTICE, web["answer"], *web["attributions"]])
            web_sources = web["sources"]
            status = "WEB_UNVERIFIED"
        else:
            if "classify_lab" not in results:
                parts.append(INSUFFICIENT_EVIDENCE_MESSAGE)
                status = "DEGRADED"
    if not parts:
        parts.append("Chọn một hồ sơ mô phỏng hoặc đặt câu hỏi cụ thể về BMI, xét nghiệm, lịch sử đo hay kiến thức đã có nguồn.")
        status = "DEGRADED"
    citations = rule_citations if "classify_lab" in results else [
        {key: item[key] for key in ("citation_id", "document_id", "chunk_id", "title", "source_url", "page")}
        for item in evidence
        if item.get("review_status") == "approved" and item.get("license_status") == "approved"
    ]
    fact_parts = parts[:]
    note_parts: list[str] = []
    # Keep KB extracts in the deterministic answer, while exposing facts and notes
    # separately so the optional composer can add only a cited explanation.
    if "search_kb" in results and evidence:
        extract_count = min(5, len(evidence))
        fact_parts = parts[:-extract_count]
        for item in evidence:
            if item.get("amended") and item.get("amended_by"):
                names = ", ".join(
                    "Quyết định 1353/QĐ-BYT" if code == "KB-01A" else str(code)
                    for code in (item.get("amended_by") or [])
                )
                note_parts.append(
                    f"Lưu ý: đoạn trích thuộc phần đã được sửa đổi bởi {names}; "
                    "cần đối chiếu văn bản sửa đổi trước khi áp dụng."
                )
        if any(item.get("excerpt_redacted") for item in evidence):
            note_parts.append(REDACTION_NOTICE)
        # The amendments and redaction notice already occur at the end of parts.
        if note_parts:
            fact_parts = parts[:len(parts) - len(note_parts) - extract_count]
    fallback_item, fallback_excerpt = _best_fallback_excerpt(evidence) if evidence else (None, None)
    if "search_kb" in results and evidence:
        deterministic_parts = list(fact_parts)
        if fallback_item is not None and fallback_excerpt is not None:
            deterministic_parts.extend([fallback_excerpt, FALLBACK_SOURCE_NOTICE])
            citations = [
                {key: fallback_item[key] for key in ("citation_id", "document_id", "chunk_id", "title", "source_url", "page")}
            ] if fallback_item.get("review_status") == "approved" and fallback_item.get("license_status") == "approved" else []
        else:
            deterministic_parts.append(INSUFFICIENT_EVIDENCE_MESSAGE)
            citations = []
            status = "DEGRADED"
        deterministic_parts.extend(note_parts)
    else:
        deterministic_parts = parts
    deterministic_answer = "\n\n".join(part for part in deterministic_parts if part)
    trace = state.get("trace", []) + [{"step": "fusion", "status": status}]
    return {
        "answer": deterministic_answer, "deterministic_answer": deterministic_answer,
        "fact_parts": fact_parts, "note_parts": note_parts, "answer_mode": "deterministic",
        "evidence": evidence, "citations": citations,
        "reference_only": reference_only, "web_sources": web_sources, "status": status, "trace": trace,
        **structured_fusion(
            ml=results.get("predict_risk"),
            clinical_rules=results.get("classify_lab"),
            evidence=evidence,
            safety_level=state.get("safety", {}).get("level", "UNKNOWN"),
            profile_type="synthetic" if state.get("profile_id") else None,
        ),
    }


def _llm_composer_node(state: AgentState) -> dict[str, Any]:
    results = state.get("results", {})
    evidence = state.get("evidence", [])
    config = get_config()
    reason = "DISABLED"
    status = state.get("status", "OK")
    answer = state.get("deterministic_answer", state.get("answer", ""))
    composition: dict[str, Any] = {}
    citations = list(state.get("citations", []))
    if "screen_risk" in results:
        reason = "SCREENING_RESULT"
    elif config.errors:
        reason = config.errors[0]
    elif config.configured:
        if state.get("status") == "NEED_CLARIFICATION":
            reason = "NEED_CLARIFICATION"
        elif medication_request(state.get("message", "")):
            reason = "MEDICATION_REQUEST"
        elif "search_kb" not in results or not evidence:
            reason = "NO_APPROVED_EVIDENCE"
        else:
            try:
                composition = compose_answer(state.get("message", ""), evidence, config=config)
            except Exception:
                composition = {"ok": False, "reason": "INTERNAL_ERROR"}
            reason = str(composition.get("reason", "INTERNAL_ERROR"))
            if composition.get("ok"):
                fact_parts = state.get("fact_parts", [])
                note_parts = state.get("note_parts", [])
                rule_citations = results.get("classify_lab", {}).get("citations", []) if "classify_lab" in results else []
                citations = []
                seen: set[str] = set()
                for citation in rule_citations:
                    valid_rule_citation = validate_citations(evidence, [citation])
                    if valid_rule_citation and citation.get("chunk_id") not in seen:
                        citations.append(valid_rule_citation[0])
                        seen.add(citation.get("chunk_id"))

                model_label_chunks: dict[int, str] = {}
                for index, citation in enumerate(composition.get("citations", []), start=1):
                    chunk_id = citation.get("chunk_id")
                    valid_model_citation = validate_citations(evidence, [citation])
                    if not valid_model_citation:
                        continue
                    if chunk_id not in seen:
                        citations.append(valid_model_citation[0])
                        seen.add(chunk_id)
                    model_label_chunks[index] = str(chunk_id)

                citations = validate_citations(evidence, citations)
                citation_labels = {
                    citation.get("chunk_id"): f"C{index}"
                    for index, citation in enumerate(citations, start=1)
                }
                label_mapping = {
                    model_label: citation_labels[chunk_id]
                    for model_label, chunk_id in model_label_chunks.items()
                    if chunk_id in citation_labels
                }
                explanation = composition["answer"]
                unresolved_labels: set[int] = set()

                def remap_label(match: re.Match[str]) -> str:
                    label_index = int(match.group(1))
                    label = label_mapping.get(label_index)
                    if label is None:
                        unresolved_labels.add(label_index)
                        return match.group(0)
                    return f"[{label}]"

                explanation = re.sub(r"\[C(\d+)\]", remap_label, explanation)
                if unresolved_labels:
                    reason = "CITATION_INVALID"
                    citations = list(state.get("citations", [])) if "classify_lab" in results else []
                    answer = state.get("deterministic_answer", state.get("answer", ""))
                else:
                    citations = [
                        {**citation, "display_label": citation_labels.get(citation.get("chunk_id"))}
                        for citation in citations
                    ]
                    answer_parts = [*fact_parts, explanation, *note_parts]
                    status = "OK"
                    llm_trace = {
                        "step": "llm_composer", "status": "OK", "mode": "llm_cited",
                        "data_level": composition.get("data_level", config.data_level), "reason": "OK",
                        "model": composition.get("model"), "latency_ms": composition.get("latency_ms"),
                        "input_tokens": composition.get("input_tokens"), "output_tokens": composition.get("output_tokens"),
                        "stop_reason": composition.get("stop_reason"),
                        "question_masked": composition.get("question_masked"),
                        "question_truncated": composition.get("question_truncated"),
                        "api_call_attempted": bool(composition.get("request_attempted", False)),
                    }
                    return {
                        "answer": "\n\n".join(part for part in answer_parts if part),
                        "citations": citations, "answer_mode": "llm_cited",
                        "llm": llm_trace,
                        "trace": state.get("trace", []) + [llm_trace],
                    }
            if reason == "MODEL_INSUFFICIENT_EVIDENCE":
                status = "DEGRADED"
                answer = state.get("deterministic_answer", state.get("answer", ""))
            else:
                answer = state.get("deterministic_answer", state.get("answer", ""))
    else:
        answer = state.get("deterministic_answer", state.get("answer", ""))

    llm_trace = {
        "step": "llm_composer",
        "status": "DEGRADED" if reason == "MODEL_INSUFFICIENT_EVIDENCE" else "FALLBACK",
        "mode": "deterministic",
        "data_level": config.data_level, "reason": reason,
        "model": composition.get("model"), "latency_ms": composition.get("latency_ms"),
        "input_tokens": composition.get("input_tokens"), "output_tokens": composition.get("output_tokens"),
        "stop_reason": composition.get("stop_reason"),
        "question_masked": composition.get("question_masked"),
        "question_truncated": composition.get("question_truncated"),
        "api_call_attempted": bool(composition.get("request_attempted", False)),
    }
    return {
        "answer": answer, "status": status, "answer_mode": "deterministic", "citations": citations,
        "llm": llm_trace, "trace": state.get("trace", []) + [llm_trace],
    }


def _validate_output_node(state: AgentState) -> dict[str, Any]:
    citations = validate_citations(state.get("evidence", []), state.get("citations", []))
    if state.get("safety", {}).get("level") == "EMERGENCY":
        return {"answer": EMERGENCY_MESSAGE, "citations": [], "evidence": [], "web_sources": [], "status": "EMERGENCY",
                "trace": state.get("trace", []) + [{"step": "output_validator", "status": "EMERGENCY_TEMPLATE_VERIFIED"}]}
    if state.get("safety", {}).get("level") == "UNKNOWN":
        return {"answer": SAFETY_UNCERTAIN_MESSAGE, "citations": [], "evidence": [], "web_sources": [], "status": "SAFETY_UNCERTAIN",
                "trace": state.get("trace", []) + [{"step": "output_validator", "status": "SAFETY_UNCERTAIN_TEMPLATE_VERIFIED"}]}
    answer = state.get("answer", "")
    if contains_medication_dose(answer):
        safety = dict(state.get("safety", {}))
        safety.update({"level": "CLINICAL_REVIEW", "output_guard": "medication_advice_blocked"})
        return {
            "answer": MEDICATION_REFUSAL_MESSAGE, "status": "CLINICAL_REVIEW", "answer_mode": "deterministic", "safety": safety,
            "tool_calls": [], "evidence": [], "citations": [], "web_sources": [],
            "trace": state.get("trace", []) + [{"step": "medication_advice_guard", "status": "BLOCKED"}],
        }
    return {"citations": citations, "trace": state.get("trace", []) + [{"step": "output_validator", "status": "CITATIONS_VALIDATED"}]}


def _build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("safety_gate", _safety_node)
    workflow.add_node("emergency_response", _emergency_node)
    workflow.add_node("safety_uncertain", _safety_uncertain_node)
    workflow.add_node("medication_refusal", _refusal_node)
    workflow.add_node("unit_clarification", _unit_clarification_node)
    workflow.add_node("guidance", _guidance_node)
    workflow.add_node("intent_router", _route_node)
    workflow.add_node("tools", _execute_tools_node)
    workflow.add_node("fusion", _compose_node)
    workflow.add_node("llm_composer", _llm_composer_node)
    workflow.add_node("output_validator", _validate_output_node)
    workflow.add_edge(START, "safety_gate")
    workflow.add_conditional_edges("safety_gate", _safety_route, {
        "emergency": "emergency_response", "uncertain": "safety_uncertain", "refusal": "medication_refusal",
        "unit_clarification": "unit_clarification", "guidance": "guidance", "continue": "intent_router",
    })
    workflow.add_edge("emergency_response", END)
    workflow.add_edge("safety_uncertain", "output_validator")
    workflow.add_edge("medication_refusal", "output_validator")
    workflow.add_edge("unit_clarification", "output_validator")
    workflow.add_edge("guidance", "output_validator")
    workflow.add_edge("intent_router", "tools")
    workflow.add_edge("tools", "fusion")
    workflow.add_edge("fusion", "llm_composer")
    workflow.add_edge("llm_composer", "output_validator")
    workflow.add_edge("output_validator", END)
    return workflow.compile()


agent_graph = _build_graph()


def run_agent(message: str, profile_id: str | None, db: Any) -> dict[str, Any]:
    output = agent_graph.invoke({"message": message, "profile_id": profile_id, "db": db})
    return {
        "status": output.get("status", "OK"), "answer": output.get("answer", ""),
        "answer_mode": output.get("answer_mode", "deterministic"),
        "safety": output.get("safety", {"level": "UNKNOWN"}),
        "safety_level": output.get("safety_level", output.get("safety", {}).get("level", "UNKNOWN")),
        "trace": output.get("trace", []),
        "intent": output.get("intent"), "tool_calls": output.get("tool_calls", []),
        "evidence": output.get("evidence", []), "citations": output.get("citations", []),
        "reference_only": output.get("reference_only", []),
        "web_sources": output.get("web_sources", []),
        "ml": output.get("ml", {"status": "NOT_REQUESTED"}),
        "clinical_rules": output.get("clinical_rules", {"status": "NOT_REQUESTED"}),
        "profile_type": output.get("profile_type", "synthetic" if profile_id else None),
    }

