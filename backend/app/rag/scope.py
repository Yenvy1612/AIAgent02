from __future__ import annotations

import re

from app.safety.keyword_rules import normalize_vi

# Accent-free terms. A false refusal is safe here; answering an unrelated question is not.
_DOMAIN_TERMS = (
    "dai thao duong", "tieu duong", "dtd", "tien dtd", "diabetes", "prediabetes", "glucose",
    "duong huyet", "duong mau", "blood sugar", "hba1c", "a1c", "insulin", "metformin",
    "ha duong", "hypoglycemia", "tang duong", "ban chan", "foot", "vong mac", "retinopathy",
    "bien chung", "complication", "che do an", "an uong", "khau phan", "bua an", "dinh duong",
    "thuc don", "carbohydrate", "tinh bot", "chat xo", "plate method", "meal", "nutrition", "diet",
    "van dong", "the luc", "tap luyen", "physical activity", "exercise", "can nang", "beo phi",
    "bmi", "huyet ap", "cholesterol", "lipid", "benh khong lay", "noncommunicable", "who pen",
    "cham soc ban dau", "primary health care",
)
_DOMAIN_RE = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in _DOMAIN_TERMS) + r")\b")


def is_in_kb_scope(query: str) -> bool:
    """Deterministic scope check for paths that have no neural relevance score."""
    return bool(_DOMAIN_RE.search(normalize_vi(query)))
