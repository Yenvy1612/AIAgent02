from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.rag.retriever import knowledge_base
from app.safety.keyword_rules import normalize_vi

SCREENING_CHUNK_ID = "KB-32-c329ac9f-012-0009"
THRESHOLD = 5
_FIELD_MAX = {
    "age": 3, "gender": 1, "gestational_diabetes": 1, "family_history": 1,
    "hypertension": 1, "activity": 1, "bmi": 3,
}
_FIELD_LABELS = {
    "age": "tuổi", "gender": "giới tính", "gestational_diabetes": "tiền sử đái tháo đường thai kỳ",
    "family_history": "cha, mẹ, anh, chị, em ruột hoặc con đẻ mắc đái tháo đường",
    "hypertension": "tiền sử tăng huyết áp", "activity": "mức độ vận động", "bmi": "BMI",
}
_DIABETES = re.compile(r"\b(?:dai thao duong|tieu duong|dtd)\b")
_GDM = re.compile(r"\b(?:dai thao duong|tieu duong|dtd) thai k(?:y|i)\b")
_FIRST_DEGREE = re.compile(
    r"\b(?:cha|bo|ba|me|anh(?: chi)? em ruot|chi em ruot|con(?: de| ruot)?)\b"
)
_OUTSIDE_RELATIVES = re.compile(r"\b(?:bà|ông|bác|cô|chú|dì|cậu|mợ)\b", re.IGNORECASE)
_BMI_VALUE = re.compile(r"\bbmi\s*(?:(?:la)\s*|[:=]\s*)?(\d{1,2}(?:[.,]\d+)?)\b")
_AGE_VALUE = re.compile(r"\b(\d{1,3})\s*(?:tuoi|t)\b|\btuoi\s*(?:la\s*)?(\d{1,3})\b")
_SELF_RISK = re.compile(
    r"\b(?:toi|minh|em)\b[^.!?\n]{0,40}\bnguy co\b[^.!?\n]{0,35}\b(?:khong|khong\?|khong vay)\b"
    r"|\b(?:tinh diem|kiem tra|danh gia)\b[^.!?\n]{0,25}\bnguy co\b[^.!?\n]{0,20}\b(?:toi|minh|em)\b"
    r"|\b(?:bang hoi|phieu)\b[^.!?\n]{0,30}\bnguy co\b[^.!?\n]{0,35}\b(?:ap dung|phu hop)\b"
    r"|\b(?:toi|minh|em)\b[^.!?\n]{0,35}\b(?:muon biet|hoi ve)\b[^.!?\n]{0,20}\bnguy co\b"
)
_GENERAL_RISK_QUESTION = re.compile(r"\b(?:yeu to nguy co|nguy co cua|nhung nguy co nao)\b")
_DIABETES_DIAGNOSIS = re.compile(
    r"\b(?:toi|minh|em)\s+(?:dang\s+)?(?:da\s+duoc\s+chan\s+doan|duoc\s+chan\s+doan|mac(?:\s+benh)?|bi(?:\s+benh)?)\s+(?:dai thao duong|tieu duong|dtd)\b"
)
_PREGNANCY = re.compile(r"\b(?:(?:toi|minh|em)\s+)?(?:hien\s+)?dang\s+(?:mang thai|co thai|co bau)\b")
_NO_FIRST_DEGREE_HISTORY = re.compile(
    r"\bkhong co (?:nguoi than bac mot|nguoi than|ai trong gia dinh)\b[^.!?\n]{0,40}\b(?:mac|bi)\b"
)


def _clause_before(text: str, position: int) -> str:
    start = max((text.rfind(mark, 0, position) for mark in (".", "?", "!", ";", "\n")), default=-1) + 1
    return text[max(start, position - 70):position]


def _negated_before(text: str, position: int) -> bool:
    return bool(re.search(
        r"\b(?:khong|chua|khong duoc|chua duoc)\b[^.!?;\n]{0,45}$",
        _clause_before(text, position),
    ))


def _age(text: str) -> int | None:
    match = _AGE_VALUE.search(text)
    if not match:
        return None
    value = int(match.group(1) or match.group(2))
    return value if value <= 120 else None


def _gender(text: str) -> str | None:
    if re.search(r"\b(?:toi|minh|em)\s+(?:la\s+)?nam\b|\bla nam\b|\bnam gioi\b", text):
        return "male"
    if re.search(r"\b(?:toi|minh|em)\s+(?:la\s+)?nu\b|\bla nu\b|\bnu gioi\b|\bnu\b", text):
        return "female"
    return None


def _gestational_diabetes(text: str) -> bool | None:
    match = _GDM.search(text)
    if not match:
        return None
    if _negated_before(text, match.start()):
        return False
    context = text[max(0, match.start() - 70):match.end() + 40]
    return True if re.search(r"\b(?:toi|minh|em|co|tung|da tung|tien su)\b", context) else None


def _family_history(message: str, text: str) -> tuple[bool | None, list[str]]:
    raw = unicodedata.normalize("NFC", message)
    outside = list(dict.fromkeys(match.group(0).lower() for match in _OUTSIDE_RELATIVES.finditer(raw)))
    family_text = normalize_vi(_OUTSIDE_RELATIVES.sub(" relativeoutside ", raw))
    if _NO_FIRST_DEGREE_HISTORY.search(family_text):
        return False, outside
    relatives = list(_FIRST_DEGREE.finditer(family_text))
    illnesses = list(_DIABETES.finditer(family_text))
    positive = False
    negative = False
    for relative in relatives:
        for illness in illnesses:
            if abs(illness.start() - relative.end()) > 100:
                continue
            if _negated_before(family_text, illness.start()):
                negative = True
            else:
                positive = True
    if positive:
        return True, outside
    if negative or (outside and illnesses):
        return False, outside
    return None, outside


def _activity(text: str) -> int | None:
    inactive = re.search(r"\b(?:it van dong|khong van dong|khong thuong xuyen van dong|it tap(?: luyen| the duc)?)\b", text)
    if inactive:
        return 1
    active = re.search(r"\b(?:thuong xuyen van dong|van dong thuong xuyen|tap the duc deu dan|tap luyen deu dan)\b", text)
    return 0 if active else None


def _bmi_score(text: str) -> int | None:
    match = _BMI_VALUE.search(text)
    if match:
        value = float(match.group(1).replace(",", "."))
        return 0 if value < 23 else 1 if value < 25 else 2 if value < 30 else 3
    if re.search(r"\b(?:khong thua can|khong bi thua can|binh thuong khong thua can)\b", text):
        return 0
    return None


def _factors(message: str) -> tuple[dict[str, Any], list[str]]:
    raw = unicodedata.normalize("NFC", message)
    text = normalize_vi(raw)
    age = _age(text)
    gender = _gender(text)
    factors: dict[str, Any] = {
        "age": age,
        "gender": gender,
        "gestational_diabetes": _gestational_diabetes(text),
        "family_history": None,
        "hypertension": None,
        "activity": _activity(text),
        "bmi": _bmi_score(text),
    }
    factors["family_history"], outside = _family_history(raw, text)
    hypertension = re.search(r"\b(?:tang huyet ap|cao huyet ap|hypertension)\b", text)
    if hypertension:
        factors["hypertension"] = not _negated_before(text, hypertension.start())
    elif re.search(r"\b(?:chua|khong)\s+(?:bi\s+)?(?:tang huyet ap|cao huyet ap)\b", text):
        factors["hypertension"] = False
    if gender == "male" and factors["gestational_diabetes"] is None:
        factors["gestational_diabetes"] = False
    scores: dict[str, int | None] = {
        "age": None if age is None else 0 if age < 40 else 1 if age < 50 else 2 if age < 60 else 3,
        "gender": None if gender is None else 1 if gender == "male" else 0,
        "gestational_diabetes": None if factors["gestational_diabetes"] is None else int(factors["gestational_diabetes"]),
        "family_history": None if factors["family_history"] is None else int(factors["family_history"]),
        "hypertension": None if factors["hypertension"] is None else int(factors["hypertension"]),
        "activity": factors["activity"],
        "bmi": factors["bmi"],
    }
    if gender == "male" and scores["gestational_diabetes"] is None:
        scores["gestational_diabetes"] = 0
    return {"values": factors, "scores": scores}, outside


def should_screen_risk(message: str) -> bool:
    text = normalize_vi(message)
    if _GENERAL_RISK_QUESTION.search(text):
        return False
    if _SELF_RISK.search(text):
        return True
    parsed, _ = _factors(message)
    return sum(value is not None for value in parsed["values"].values()) >= 2


def _screening_source() -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    chunk = next((
        item for item in knowledge_base._approved_chunks()
        if item.get("chunk_id") == SCREENING_CHUNK_ID and item.get("document_id") == "KB-32"
    ), None)
    if not chunk:
        return None
    evidence = {
        "citation_id": "C1", "document_id": chunk["document_id"], "chunk_id": chunk["chunk_id"],
        "title": chunk["title"], "source_url": chunk.get("source_url"), "page": chunk.get("page"),
        "topic": chunk.get("topic"), "excerpt": chunk["text"],
        "review_status": chunk["review_status"], "license_status": chunk["license_status"],
        "document_version": chunk.get("document_version"), "section": chunk.get("section"),
    }
    citation = {key: evidence[key] for key in (
        "citation_id", "document_id", "chunk_id", "title", "source_url", "page",
    )}
    citation["display_label"] = "C1"
    return [evidence], [citation]


def _score_range(scores: dict[str, int | None]) -> tuple[int, int]:
    known = sum(value for value in scores.values() if value is not None)
    unknown = {key for key, value in scores.items() if value is None}
    minimum = known
    maximum = known + sum(_FIELD_MAX[key] for key in unknown)
    if "gender" in unknown and "gestational_diabetes" in unknown:
        maximum -= 1  # A man can score for sex; a woman can score for gestational diabetes.
    return minimum, maximum


def _format_answer(
    scores: dict[str, int | None], minimum: int, maximum: int, missing: list[str],
    outside: list[str], excluded: list[str],
) -> tuple[str, str]:
    if excluded:
        reasons = {
            "diabetes_diagnosed": "bạn đã được chẩn đoán đái tháo đường",
            "pregnancy": "bạn đang mang thai",
            "under_18": "bạn dưới 18 tuổi",
        }
        why = "; ".join(reasons[item] for item in excluded)
        body = f"Bảng hỏi này không chấm điểm trong trường hợp {why}."
        status = "NOT_SCORED"
    elif minimum < THRESHOLD <= maximum:
        labels = ", ".join(_FIELD_LABELS[item] for item in missing)
        body = (
            f"Theo bảng hỏi sàng lọc trong Quyết định 3087/QĐ-BYT, khoảng điểm hiện tại là "
            f"{minimum}–{maximum}; khoảng này đi qua ngưỡng 5 nên chưa thể kết luận. "
            f"Bạn hãy gửi thêm: {labels}."
        )
        status = "NEED_INFORMATION"
    elif minimum >= THRESHOLD:
        body = (
            f"Theo bảng hỏi sàng lọc trong Quyết định 3087/QĐ-BYT, khoảng điểm của bạn là "
            f"{minimum}–{maximum}, từ ngưỡng 5 nên thuộc nhóm nguy cơ cao theo bảng hỏi. "
            "Bạn nên đi khám để kiểm tra đường huyết."
        )
        status = "OK"
    else:
        missing_count = sum(value is None for value in scores.values())
        if minimum == maximum:
            score_text = f"{minimum} điểm"
        elif scores.get("gender") is None and missing_count == 1:
            score_text = f"{minimum} điểm, hoặc {maximum} điểm nếu là nam"
        else:
            score_text = f"khoảng điểm hiện tại là {minimum}–{maximum}"
        body = (
            f"Theo bảng hỏi sàng lọc trong Quyết định 3087/QĐ-BYT, bạn được {score_text}. "
            f"Mức này dưới ngưỡng 5 điểm, tức chưa thuộc nhóm nguy cơ cao theo bảng hỏi."
        )
        status = "OK"
    if outside:
        if any(item == "bà" for item in outside):
            body += " Lưu ý: bà không được tính, vì bảng hỏi chỉ tính cha, mẹ, anh, chị, em ruột và con đẻ."
        else:
            body += " Lưu ý: ông/bác/cô/chú/dì/cậu/mợ không nằm trong nhóm thân nhân được tính ở bảng hỏi."
    body += " Đây là bảng hỏi tham khảo, không phải chẩn đoán. [C1]"
    return body, status


def screen_risk(message: str) -> dict[str, Any]:
    if not should_screen_risk(message):
        return {"status": "NOT_REQUESTED", "answer": "Chưa có yêu cầu chấm bảng hỏi nguy cơ.", "evidence": [], "citations": []}
    source = _screening_source()
    if source is None:
        return {
            "status": "SOURCE_MISSING", "score_min": None, "score_max": None,
            "answer": f"Không thể chấm điểm vì không tìm thấy nguồn đã duyệt {SCREENING_CHUNK_ID} trong Knowledge Base. Đây là bảng hỏi tham khảo, không phải chẩn đoán.",
            "evidence": [], "citations": [],
        }
    evidence, citations = source
    parsed, outside = _factors(message)
    values, scores = parsed["values"], parsed["scores"]
    minimum, maximum = _score_range(scores)
    excluded: list[str] = []
    diagnosis = _DIABETES_DIAGNOSIS.search(normalize_vi(message))
    if diagnosis and not _negated_before(normalize_vi(message), diagnosis.start()):
        excluded.append("diabetes_diagnosed")
    normalized = normalize_vi(message)
    pregnant = _PREGNANCY.search(normalized)
    if pregnant and not _negated_before(normalized, pregnant.start()):
        excluded.append("pregnancy")
    if values["age"] is not None and values["age"] < 18:
        excluded.append("under_18")
    missing = [key for key, value in scores.items() if value is None]
    answer, status = _format_answer(scores, minimum, maximum, missing, outside, excluded)
    return {
        "status": status, "score_min": None if excluded else minimum,
        "score_max": None if excluded else maximum, "scores": scores,
        "missing_factors": [_FIELD_LABELS[key] for key in missing],
        "excluded_reasons": excluded, "answer": answer,
        "evidence": evidence, "citations": citations,
    }
