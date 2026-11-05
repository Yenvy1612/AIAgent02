from __future__ import annotations

import re

from app.safety.keyword_rules import normalize_vi

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
_ANALYTE_NAME = re.compile(r"(?<![a-z])(?:hba1c|a1c)", re.IGNORECASE)
_NUMBER_VALUE = re.compile(r"\d+(?:[.,]\d+)?")
_TYPE_WORD = re.compile(r"\b(?:type|typ|tip)\s*$")


def _mask_numeric_values(value: str) -> tuple[str, bool]:
    """Mask every number, retaining only diabetes type labels and A1C name digits."""
    analyte_digits = {
        analyte.start() + digit.start()
        for analyte in _ANALYTE_NAME.finditer(value)
        for digit in re.finditer(r"\d", analyte.group())
    }
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        number = match.group()
        if match.start() in analyte_digits:
            return match.group(0)
        prefix = normalize_vi(value[:match.start()])
        if number.isdigit() and _TYPE_WORD.search(prefix):
            return match.group(0)
        changed = True
        return "[giá trị đã ẩn]"

    return _NUMBER_VALUE.sub(replace, value), changed


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

    value, count = _mask_numeric_values(value)
    redacted = redacted or count

    truncated = len(value) > max_chars
    return {"question": value[:max_chars], "masked": redacted, "truncated": truncated}
