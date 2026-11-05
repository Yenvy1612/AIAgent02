from __future__ import annotations

import re

_HBA1C = re.compile(r"(\b(?:hba1c|a1c)\b[^0-9]{0,12})\d{1,2}(?:[.,]\d+)?\s*(?:mmol\s*/?\s*mol|%)?", re.IGNORECASE)
_GLUCOSE = re.compile(
    r"(\b(?:glucose|đường\s+huyết|đường\s+máu)\b\D{0,24})"
    r"\d{1,4}(?:[.,]\d+)?\s*(?:mg\s*/?\s*dl|mmol\s*/?\s*l)?",
    re.IGNORECASE,
)
_BMI = (
    re.compile(r"\b\d{2,3}(?:[.,]\d+)?\s*kg\D{0,20}\d{2,3}(?:[.,]\d+)?\s*cm\b", re.IGNORECASE),
    re.compile(r"\b\d{2,3}(?:[.,]\d+)?\s*cm\D{0,20}\d{2,3}(?:[.,]\d+)?\s*kg\b", re.IGNORECASE),
)
_BMI_SCORE = re.compile(r"(\bbmi\b\D{0,12})\d{1,2}(?:[.,]\d+)?", re.IGNORECASE)
_MODEL_SCORE = re.compile(
    r"(\b(?:model\s+score|risk\s+score|score|shap|điểm(?:\s+mô\s+hình|\s+nguy\s+cơ)?|đóng\s+góp)\b\D{0,16})"
    r"[+-]?\d+(?:[.,]\d+)?",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_DEMO_ID = re.compile(r"\bDEMO\s*[-–—]\s*\d{2}\b", re.IGNORECASE)
_LONG_ID = re.compile(r"(?<!\d)(?:\d[\s.-]?){8,14}\d(?!\d)")
_PHONE = re.compile(r"(?<!\w)(?:\+?84|0)(?:[\s().-]*\d){8,10}(?!\w)")


def mask_question(message: str, *, max_chars: int = 2000) -> dict[str, object]:
    """Mask common measurements and direct identifiers without retaining the original in traces."""
    value = str(message)
    redacted = False

    for pattern, replacement in (
        (_HBA1C, r"\1[giá trị đã ẩn]"),
        (_GLUCOSE, r"\1[giá trị đã ẩn]"),
    ):
        value, count = pattern.subn(replacement, value)
        redacted = redacted or count > 0
    for pattern in _BMI:
        value, count = pattern.subn("[chỉ số đã ẩn]", value)
        redacted = redacted or count > 0
    for pattern in (_BMI_SCORE, _MODEL_SCORE):
        value, count = pattern.subn(r"\1[giá trị đã ẩn]", value)
        redacted = redacted or count > 0
    for pattern in (_EMAIL, _DEMO_ID, _PHONE, _LONG_ID):
        value, count = pattern.subn("[định danh đã ẩn]", value)
        redacted = redacted or count > 0

    truncated = len(value) > max_chars
    return {"question": value[:max_chars], "masked": redacted, "truncated": truncated}
