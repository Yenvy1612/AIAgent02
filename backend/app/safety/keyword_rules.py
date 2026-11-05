from __future__ import annotations

import re
import unicodedata


def normalize_vi(value: str) -> str:
    value = value.lower().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", value).strip()


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 30):start]
    return any(re.search(pattern, prefix) for pattern in (
        r"(?:khong|chua)\s+(?:(?:ai|nguoi nao)\s+)?(?:(?:bi|co|dang|gap)\s+)?$",
        r"(?:not|no|never|without)\s+(?:(?:having|experiencing)\s+)?(?:a|an|the)?\s*$",
        r"(?:no one|nobody)\s+(?:is\s+)?(?:having|experiencing|currently\s+having)?\s*$",
        r"(?:dont|don't)\s+(?:have|feel|experience)\s+(?:any\s+)?$",
    ))


def _is_historical_context(text: str, start: int, end: int | None = None) -> bool:
    suffix_end = end if end is not None else start
    context = text[max(0, start - 32):min(len(text), suffix_end + 36)]
    if re.search(
        r"\b(?:tung|da tung|truoc day|luc truoc|hom qua|thang truoc|tuan truoc|nam ngoai|"
        r"yesterday|last week|last month|previously|earlier today|history of)\b",
        context,
    ):
        return True
    prefix = text[max(0, start - 90):start]
    return bool(re.search(
        r"\b(?:article|book|lesson|example|novel|fictional character)\b[^.!?]{0,70}"
        r"\b(?:lists?|mentions?|describes?|says?|shows?)\b[^.!?]{0,40}$",
        prefix,
    ))


def _contains_current_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    for phrase in phrases:
        for match in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
            if not _is_negated(text, match.start()) and not _is_historical_context(text, match.start(), match.end()):
                return True
    return False


def deterministic_emergency(message: str, glucose_value: float | None = None, glucose_unit: str | None = None) -> bool:
    text = normalize_vi(message)
    severe = (
        "bat tinh", "ngat", "co giat", "lu lan", "kho tho", "tho gap",
        "dau nguc", "khong the nuot", "khong tinh tao", "mat y thuc",
        "unconscious", "passed out", "seizure", "confusion", "shortness of breath",
        "difficulty breathing", "cannot breathe", "cant breathe", "can't breathe", "chest pain",
        "cannot swallow", "cant swallow", "can't swallow",
    )
    if _contains_current_phrase(text, severe):
        return True
    # Recognize the guideline-level DKA/HHS red-flag cluster used by the MVP
    # emergency demo without depending on the learned detector.
    very_high_glucose = _contains_current_phrase(text, (
        "duong huyet rat cao", "duong mau rat cao", "blood sugar very high", "glucose very high",
    ))
    rapid_breathing = _contains_current_phrase(text, (
        "tho nhanh", "tho gap", "rapid breathing", "deep rapid breathing",
    ))
    repeated_vomiting = _contains_current_phrase(text, (
        "non nhieu", "vomiting repeatedly", "repeated vomiting",
    ))
    abdominal_pain = _contains_current_phrase(text, ("dau bung", "abdominal pain"))
    if very_high_glucose and (rapid_breathing or (repeated_vomiting and abdominal_pain)):
        return True
    if glucose_value is not None and glucose_unit in {"mg/dL", "mmol/L"}:
        mg_dl = glucose_value if glucose_unit == "mg/dL" else glucose_value * 18.0182
        reading = re.search(r"(?:glucose|duong huyet|duong mau)\D{0,24}\d+(?:[.,]\d+)?\s*(?:mg\s*/?\s*dl|mmol\s*/?\s*l)", text)
        reading_start = reading.start() if reading else 0
        reading_end = reading.end() if reading else len(text)
        if mg_dl < 54 and not _is_historical_context(text, reading_start, reading_end):
            return True
    return False


def medication_request(message: str) -> bool:
    text = normalize_vi(message)
    patterns = (
        r"(?:tang|giam|doi|ngung|bo|dieu\s+chinh)\s+(?:lieu|dose|insulin|thuoc)",
        r"(?:lieu|dose)\s+(?:insulin|thuoc)",
        r"(?:tu\s+)?(?:tang|giam|doi|ngung|dieu\s+chinh)\s+(?:lieu|insulin|thuoc)",
        r"(?:tang|giam|doi|ngung|bo|bat\s+dau|tiep\s+tuc|dieu\s+chinh|dung|uong|tiem).{0,36}(?:insulin|metformin|thuoc)",
        r"(?:insulin|metformin|thuoc).{0,36}(?:tang|giam|doi|ngung|bo|bat\s+dau|tiep\s+tuc|dieu\s+chinh|dung|uong|tiem)",
        r"(?:insulin|thuoc).{0,24}(?:tang|giam|doi|ngung|lieu|dose)",
        r"(?:insulin|metformin|thuoc).{0,40}(?:lieu|dose|tang|giam|doi|ngung|dung)",
        r"(?:lieu|dose).{0,40}(?:insulin|metformin|thuoc)",
        r"bao\s+nhieu.{0,24}(?:insulin|metformin|thuoc)",
        r"bao\s+nhieu\s+(?:don\s+vi|unit).{0,20}(?:insulin|thuoc)",
        r"(?:insulin|metformin|thuoc).{0,40}\bchua\s+(?:khoi|dut|tri|duoc\s+(?:benh|dai\s+thao|tieu\s+duong))",
        r"\b(?:medicine|medication|drug|insulin|metformin)\b.{0,40}\bcures?\b",
        r"\b(?:how\s+much|what\s+(?:dose|dosage)|how\s+many\s+(?:units|tablets)|should\s+i\s+(?:take|use|stop|skip|change)|can\s+i\s+(?:take|use|stop|skip|change)|may\s+i\s+(?:take|use|stop|skip|change))\b.{0,48}\b(?:insulin|metformin|medicine|medication|drug|dose|dosage)\b",
        r"\b(?:should\s+i|can\s+i|may\s+i|could\s+i|do\s+i\s+need\s+to)\b.{0,48}\b(?:insulin|metformin|medicine|medication|drug|dose|dosage)\b",
        r"\b(?:increase|decrease|adjust|change|stop|skip|start|double|halve)\b.{0,36}\b(?:insulin|metformin|medicine|medication|dose|dosage)\b",
        r"\b(?:insulin|metformin|medicine|medication)\b.{0,36}\b(?:increase|decrease|adjust|change|stop|skip|start|dose|dosage|units?)\b",
        r"\b(?:khang\s+sinh|antibiotics?|glucagon)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


_WOUND = r"(?:vet\s+loet|loet\s+ban\s+chan|loet\s+chan|vet\s+thuong\s+(?:o\s+)?(?:ban\s+)?chan|foot\s+(?:ulcer|wound))"
_WOUND_CARE_PATTERNS = (
    re.compile(rf"\b(?:xu\s+tri|xu\s+ly|dieu\s+tri|chua\s+tri|cham\s+soc|thay\s+bang|bang\s+bo|rua|boi|dap|treat|dress|clean|heal)\b(?:\s+\w+){{0,3}}\s+{_WOUND}"),
    re.compile(rf"{_WOUND}.{{0,60}}\b(?:tai\s+nha|tu\s+(?:xu|chua|dieu\s+tri|cham\s+soc|boi|rua|dap)|at\s+home|myself|xu\s+tri|xu\s+ly|dieu\s+tri|thay\s+bang|boi\s+gi|dap\s+gi|treat|dress)\b"),
)


def wound_care_request(message: str) -> bool:
    """Treating an existing foot ulcer or wound needs a clinician, whatever the approved sources say."""
    text = normalize_vi(message)
    return any(pattern.search(text) for pattern in _WOUND_CARE_PATTERNS)


_DOSE_NUMBER = r"(?:\d+(?:[.,]\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|half|quarter|khong|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin|muoi|mot nua|nua)"
_DOSE_UNIT = r"(?:mg(?!\s*/?\s*dl\b)|milligrams?|mcg|micrograms?|ug|µg|μg|iu|international\s+units?|u|units?|tablets?|tabs?|pills?|capsules?|caps?|patches?|puffs?|sprays?|vien|don\s+vi)"
_DOSE_MASS_OR_VOLUME = r"(?:g|grams?|ml|milliliters?|millilitres?|drops?)"
# "dung nap" means glucose tolerance, as in the 75 g diagnostic test, not "dùng" (to use).
_DOSE_CUE = r"(?:dose|dosage|lieu|take|use|start|stop|skip|u\s+ong|dung(?!\s+nap)|ngung|tiem|dieu\s+chinh)"
_MEDICATION_CONTEXT = r"(?:insulin|metformin|medicine|medication|drug|thuoc|tablets?|tabs?|pills?|capsules?|vien|ozempic|rybelsus|trulicity|victoza|mounjaro|lantus|humalog|novolog|novolin|tresiba|toujeo|basaglar|jardiance|farxiga|invokana|glucophage|glipizide|glyburide|glimepiride|sitagliptin|januvia|linagliptin|tradjenta|empagliflozin|dapagliflozin|canagliflozin|pioglitazone|actos|repaglinide|nateglinide|exenatide|liraglutide|semaglutide|dulaglutide|tirzepatide)"
_MEDICATION_ACTION = r"(?:take|taking|use|using|inject|injecting|administer|administering|start|starting|stop|stopping|skip|skipping|continue|continuing|hold|holding|resume|resuming|uong|dung(?!\s+nap)|tiem|bat\s+dau|ngung|bo\s+qua|tiep\s+tu|tam\s+ngung)"
_MEDICATION_CHANGE = r"(?:increase|increased|increasing|decrease|decreased|decreasing|adjust|adjusted|adjusting|change|changed|changing|double|doubled|halve|halved|reduce|reduced|reducing|titrate|titrated|titrating|tang|giam|dieu\s+chinh|doi(?=\s+(?:lieu|thuoc|insulin)))"
_MEDICATION_FREQUENCY = r"(?:once|twice|(?:two|three|\d+)\s+times|daily|nightly|weekly|every\s+(?:day|night|morning|evening|\d+\s+hours?)|each\s+day|before\s+meals|after\s+meals|with\s+meals|with\s+breakfast|with\s+dinner|at\s+bedtime|q\.d\.|b\.i\.d\.|t\.i\.d\.|moi\s+ngay|hang\s+ngay|moi\s+buoi|truoc\s+an|sau\s+an|buoi\s+sang|buoi\s+toi|moi\s+toi)"
_MEDICATION_DOSE_PATTERNS = (
    re.compile(rf"(?<![\w/]){_DOSE_NUMBER}\s*{_DOSE_UNIT}\b"),
    re.compile(rf"\b(?:dose|dosage|lieu)\b(?:\s+[a-z]+){{0,4}}\s*{_DOSE_NUMBER}\b"),
    re.compile(rf"\b{_DOSE_CUE}\b.{{0,24}}(?<![\w/]){_DOSE_NUMBER}\s*{_DOSE_MASS_OR_VOLUME}\b"),
    re.compile(rf"\b{_MEDICATION_CONTEXT}\b.{{0,80}}(?<![\w/]){_DOSE_NUMBER}\s*{_DOSE_MASS_OR_VOLUME}\b"),
    re.compile(rf"(?<![\w/]){_DOSE_NUMBER}\s*{_DOSE_MASS_OR_VOLUME}\b.{{0,80}}\b{_MEDICATION_CONTEXT}\b"),
    re.compile(rf"\b{_MEDICATION_ACTION}\b[^.!?;\n]{{0,48}}\b{_MEDICATION_CONTEXT}\b"),
    re.compile(rf"\b{_MEDICATION_CHANGE}\b[^.!?;\n]{{0,32}}\b{_MEDICATION_CONTEXT}\b(?!\s+(?:resistance|sensitivity|production|secretion|levels?|concentration))"),
    re.compile(rf"\b{_MEDICATION_CONTEXT}\b(?!\s+(?:resistance|sensitivity|production|secretion|levels?|concentration))[^.!?;\n]{{0,32}}\b{_MEDICATION_CHANGE}\b"),
    re.compile(rf"\b{_MEDICATION_CONTEXT}\b[^.!?;\n]{{0,64}}\b{_MEDICATION_FREQUENCY}\b"),
    re.compile(rf"\b{_MEDICATION_FREQUENCY}\b[^.!?;\n]{{0,64}}\b{_MEDICATION_CONTEXT}\b"),
    re.compile(rf"\b(?:increase|decrease|adjust|change|double|halve|reduce|tang|giam|dieu\s+chinh|doi\s+(?:lieu|thuoc|insulin))\b[^.!?;\n]{{0,48}}\b(?:dose|dosage|lieu|amount|number\s+of\s+units?)\b"),
    re.compile(rf"\b(?:dose|dosage|lieu|amount|number\s+of\s+units?)\b[^.!?;\n]{{0,48}}\b(?:increase|decrease|adjust|change|double|halve|reduce|tang|giam|dieu\s+chinh|doi\s+(?:lieu|thuoc|insulin))\b"),
)


def contains_medication_dose(text: str) -> bool:
    """Conservatively detect medication quantities and actionable regimens in answers."""
    normalized = normalize_vi(text)
    return any(pattern.search(normalized) for pattern in _MEDICATION_DOSE_PATTERNS)


_SENTENCE_BREAK = re.compile(r"(?<=[.!?;])\s+")
# Wider than the dose patterns on purpose: treatment steps such as "ngừng điều trị khi pH > 7" name no dose.
_MEDICATION_MENTION = re.compile(
    rf"\b(?:{_MEDICATION_CONTEXT}|dose|dosage|lieu|don\s+vi|sglt-?2|dpp-?4|glp-?1|sulfonylure\w*|gliclazid\w*|acarbose|aspirin|statin\w*|glucagon|khang\s+sinh|antibiotics?|tiem|truyen|tinh\s+mach|intravenous\w*|give|given|ngung\s+dieu\s+tri|phac\s+do|regimens?)\b"
)
_TREATMENT_REGIMEN = re.compile(r"\b(?:phac\s+do|khang\s+sinh|antibiotics?)\b")


def mentions_treatment_regimen(text: str) -> bool:
    """Regimen tables can name drugs without any quantity, so the dose patterns alone miss them."""
    return bool(_TREATMENT_REGIMEN.search(normalize_vi(text)))


def redact_medication_sentences(text: str) -> str:
    """Remove every sentence that names a medication or dose. Lines stay separate so patterns cannot span them."""
    kept_lines = []
    for line in text.splitlines():
        sentences = [
            sentence.strip() for sentence in _SENTENCE_BREAK.split(line)
            if sentence.strip()
            and not contains_medication_dose(sentence)
            and not _MEDICATION_MENTION.search(normalize_vi(sentence))
        ]
        if sentences:
            kept_lines.append(" ".join(sentences))
    redacted = "\n".join(kept_lines)
    return "" if contains_medication_dose(redacted) else redacted


