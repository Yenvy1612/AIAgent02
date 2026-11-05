from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable


TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
HEADING_RE = re.compile(
    r"^\s*(#{1,6}\s+.+"
    r"|(?:CHƯƠNG|PHẦN|MỤC)\s+[^\n]{1,160}"
    r"|(?:Chương|Phần|Điều)\s+\d+\b[^\n]{0,160})\s*$"
)
NUMBERED_HEADING_RE = re.compile(
    r"^(?:\d{1,2}\.\s|\d{1,2}\.\s?\d{1,2}(?:\.\s?\d{1,2})*\.?\s|[IVXLC]+\.\s)\s*[A-ZÀ-ỴĐ]"
)
MAX_INFERRED_HEADING_CHARS = 80
MIN_TAIL_TOKENS = 100
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=(?:[A-ZÀ-ỴĐ]|\d|[“\"(]))")
KEEP_WITH_PREVIOUS_RE = re.compile(r"^(?:ngoại trừ|trừ trường hợp|lưu ý|tuy nhiên|except|unless|however|but)\b", re.I)
TABLE_LINE_RE = re.compile(r"^\s*(?:\|.*\||[-+|: ]{4,})\s*$")


def lexical_token_count(text: str) -> int:
    """Deterministic fallback; production can inject the local model tokenizer."""
    return len(TOKEN_RE.findall(text))


@dataclass
class Unit:
    text: str
    section: str
    page: int | None
    table: bool = False


def _heading_title(line: str) -> str | None:
    """Return a section title when one extracted line is a heading, otherwise None."""
    stripped = line.strip()
    explicit = HEADING_RE.match(stripped)
    if explicit:
        return explicit.group(1).lstrip("# ").strip()
    # Wide gaps come from flattened table or flowchart columns, not titles.
    if len(stripped) > MAX_INFERRED_HEADING_CHARS or stripped[-1] in ".;,:" or re.search(r"\s{3,}", stripped):
        return None
    if NUMBERED_HEADING_RE.match(stripped):
        return stripped
    letters = [ch for ch in stripped if ch.isalpha()]
    if (
        len(letters) >= 8 and all(ch.isupper() for ch in letters)
        and len(stripped.split()) >= 2 and not any(ch.isdigit() for ch in stripped)
    ):
        return stripped
    return None


def _text_blocks(text: str, page: int | None, initial_section: str = "") -> list[Unit]:
    paragraphs: list[tuple[str, bool]] = []
    current: list[str] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(("\n".join(current).strip(), in_table))
                current, in_table = [], False
            continue
        is_table = bool(TABLE_LINE_RE.match(line))
        # PDF pages rarely have blank lines, so headings are detected per line.
        if not is_table and _heading_title(stripped):
            if current:
                paragraphs.append(("\n".join(current).strip(), in_table))
                current, in_table = [], False
            paragraphs.append((stripped, False))
            continue
        if current and is_table != in_table:
            paragraphs.append(("\n".join(current).strip(), in_table))
            current = []
        in_table = is_table
        current.append(line.rstrip())
    if current:
        paragraphs.append(("\n".join(current).strip(), in_table))

    section = initial_section
    units: list[Unit] = []
    for paragraph, is_table in paragraphs:
        heading = None if "\n" in paragraph or is_table else _heading_title(paragraph)
        if heading:
            section = heading
            units.append(Unit(paragraph, section, page))
        elif is_table:
            units.append(Unit(paragraph, section, page, table=True))
        else:
            flattened = re.sub(r"\s+", " ", paragraph)
            sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(flattened) if part.strip()]
            for sentence in sentences:
                if KEEP_WITH_PREVIOUS_RE.match(sentence) and units and units[-1].page == page:
                    units[-1].text = f"{units[-1].text} {sentence}"
                else:
                    units.append(Unit(sentence, section, page))
    return units


def _split_oversized_unit(unit: Unit, limit: int, counter: Callable[[str], int]) -> list[Unit]:
    # Tables remain whole so their headings, columns, values, and units stay together.
    if unit.table or counter(unit.text) <= limit:
        return [unit]
    parts = [part.strip() for part in re.split(r"(?<=[;；])\s+", unit.text) if part.strip()]
    pieces: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current} {part}".strip()
        if current and counter(candidate) > limit:
            pieces.append(current)
            current = part
        else:
            current = candidate
    if current:
        pieces.append(current)
    result: list[Unit] = []
    for piece in pieces:
        if counter(piece) <= limit:
            result.append(Unit(piece, unit.section, unit.page))
            continue
        words = piece.split()
        start = 0
        while start < len(words):
            end, best = start + 1, start + 1
            while end <= len(words) and counter(" ".join(words[start:end])) <= limit:
                best, end = end, end + 1
            result.append(Unit(" ".join(words[start:best]), unit.section, unit.page))
            start = best
    return result


def _overlap_text(units: list[Unit], target: int, counter: Callable[[str], int]) -> str:
    candidates: list[str] = []
    for unit in reversed(units):
        if unit.table:
            break
        candidates.insert(0, unit.text)
        joined = " ".join(candidates)
        if counter(joined) >= target:
            return joined
    joined = " ".join(candidates)
    if counter(joined) < 60:
        return ""
    # Sentence granularity can overshoot 80; trim from the left at a word boundary.
    words = joined.split()
    while words and counter(" ".join(words)) > 80:
        words.pop(0)
    overlap = " ".join(words)
    return overlap if 60 <= counter(overlap) <= 80 else ""


def chunk_page(
    text: str,
    page: int | None,
    *,
    min_tokens: int = 350,
    max_tokens: int = 600,
    overlap_tokens: int = 70,
    token_counter: Callable[[str], int] | None = None,
    initial_section: str = "",
) -> list[dict[str, Any]]:
    if not 60 <= overlap_tokens <= 80:
        raise ValueError("Chunk overlap must be between 60 and 80 tokens.")
    if min_tokens < 1 or max_tokens < min_tokens:
        raise ValueError("Chunk token bounds are invalid.")
    counter = token_counter or lexical_token_count
    units = _text_blocks(text, page, initial_section)
    split_limit = max(1, max_tokens - overlap_tokens)
    expanded = [piece for unit in units for piece in _split_oversized_unit(unit, split_limit, counter)]
    output: list[dict[str, Any]] = []
    current: list[Unit] = []
    prefix = ""

    def record(chunk_units: list[Unit], overlap: str) -> dict[str, Any]:
        body_parts = ([overlap] if overlap else []) + [unit.text for unit in chunk_units]
        body = "\n".join(part for part in body_parts if part).strip()
        sections = list(dict.fromkeys(unit.section for unit in chunk_units if unit.section))
        if overlap and not sections:
            sections = list(dict.fromkeys(unit.section for unit in units if unit.section))[-1:]
        return {
            "text": body,
            "page": page,
            "section": " / ".join(sections) if sections else initial_section or None,
            "token_count": counter(body),
            "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }

    def flush() -> list[Unit]:
        nonlocal current, prefix
        completed, prior_prefix = current, prefix
        output.append(record(completed, prior_prefix))
        current, prefix = [], ""
        return completed

    for unit in expanded:
        candidate = ([prefix] if prefix else []) + [item.text for item in current] + [unit.text]
        candidate_count = counter("\n".join(candidate))
        if current and candidate_count > max_tokens:
            previous = current
            flush()
            prefix = _overlap_text(previous, overlap_tokens, counter)
            candidate = ([prefix] if prefix else []) + [unit.text]
            # An indivisible table may exceed the target; preserve it and its context.
            if counter("\n".join(candidate)) > max_tokens:
                prefix = ""
        current.append(unit)

    if current:
        tail = record(current, prefix)
        if output and tail["token_count"] < MIN_TAIL_TOKENS:
            # A short page tail reads better appended to the previous chunk, without repeating the overlap.
            merged_text = "\n".join([output[-1]["text"], *(unit.text for unit in current)])
            if counter(merged_text) <= max_tokens:
                merged_sections = list(dict.fromkeys(
                    part for part in (*(output[-1]["section"] or "").split(" / "), tail["section"] or "") if part
                ))
                output[-1] = {
                    **output[-1],
                    "text": merged_text,
                    "section": " / ".join(merged_sections) or None,
                    "token_count": counter(merged_text),
                    "content_hash": hashlib.sha256(merged_text.encode("utf-8")).hexdigest(),
                }
                return output
        output.append(tail)
    return output


def chunk_pages(pages: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    section = ""
    for page_record in pages:
        page_chunks = chunk_page(page_record.get("text", ""), page_record.get("page"), initial_section=section, **kwargs)
        for chunk in page_chunks:
            if chunk.get("section"):
                section = str(chunk["section"]).split(" / ")[-1]
            result.append(chunk)
    return result
