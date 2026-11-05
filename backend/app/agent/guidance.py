from __future__ import annotations

import re

from app.safety.keyword_rules import normalize_vi

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Không đủ thông tin đáng tin cậy đã được duyệt trong Knowledge Base để trả lời câu hỏi này. "
    "Bạn có thể hỏi cụ thể hơn về đái tháo đường, hoặc gõ \"hướng dẫn\" để xem mình giúp được gì."
)

_USAGE = (
    "- Hỏi kiến thức: \"HbA1c là gì?\"\n"
    "- Diễn giải xét nghiệm: \"HbA1c 6.2%\" hoặc \"glucose lúc đói 126 mg/dL\". "
    "Hãy ghi rõ đơn vị và thời điểm đo.\n"
    "- Tính BMI: \"70 kg, 170 cm\".\n"
    "- Xem lịch sử đo hoặc kết quả mô hình nghiên cứu: chọn một hồ sơ mô phỏng, "
    "rồi nhập \"lịch sử đo\" hoặc \"đánh giá hồ sơ\".\n"
    "Đây là bản demo: mình không chẩn đoán, không tư vấn liều thuốc, "
    "và bạn không nên nhập dữ liệu bệnh nhân thật. Nếu có triệu chứng nguy hiểm, hãy gọi 115."
)
_LAB_INPUT = (
    "Để diễn giải, mình cần chỉ số cụ thể. Bạn hãy nhập theo một trong hai mẫu:\n"
    "- HbA1c kèm %: \"HbA1c 6.2%\".\n"
    "- Glucose kèm đơn vị và thời điểm đo (lúc đói, ngẫu nhiên, hoặc sau nghiệm pháp 2 giờ): "
    "\"glucose lúc đói 126 mg/dL\".\n"
    "Mình chỉ đối chiếu với ngưỡng tham khảo, kết quả không phải chẩn đoán."
)
_TEMPLATES = {
    "greeting": "Chào bạn! Mình là DiaCare AI, trợ lý giáo dục về đái tháo đường type 2. Bạn có thể bắt đầu như sau:\n" + _USAGE,
    "usage": "Mình là DiaCare AI, trợ lý giáo dục về đái tháo đường type 2. Bạn có thể dùng mình như sau:\n" + _USAGE,
    "thanks": "Không có gì! Bạn cần tìm hiểu thêm điều gì cứ hỏi nhé. Gõ \"hướng dẫn\" nếu muốn xem mình giúp được gì.",
    "goodbye": "Tạm biệt bạn! Khi cần tìm hiểu thêm về đái tháo đường, bạn cứ quay lại nhé.",
    "lab_input": _LAB_INPUT,
}
_PROFILE_NOTE = "Bạn đang chọn một hồ sơ mô phỏng, nên có thể hỏi ngay \"lịch sử đo\" hoặc \"đánh giá hồ sơ\"."

_ADDRESS = r"(?: (?:ban|diacare|em|anh|chi|bac si|ad|oi|a|nhe|nha|nhi|voi))*"
_GREETING = r"(?:xin chao|chao|hello|helo|hi|hey|alo)"
_GREETING_ONLY = re.compile(rf"^{_GREETING}{_ADDRESS}$")
_GREETING_PREFIX = re.compile(rf"^{_GREETING}{_ADDRESS} ")
_THANKS = re.compile(rf"^(?:cam on|cam on nhieu|thanks|thank you|thank){_ADDRESS}$")
_GOODBYE = re.compile(rf"^(?:tam biet|bye|bye bye|goodbye|hen gap lai){_ADDRESS}$")
_USAGE_REQUEST = re.compile(
    r"^(?:(?:huong dan|cach dung|cach su dung|help|menu|tro giup)(?: su dung| toi| minh)?"
    r"|(?:(?:ban|diacare|em) )?la ai"
    r"|(?:(?:ban|diacare|em) )?(?:co the )?(?:lam|giup)(?: duoc)?(?: cho (?:toi|minh))?(?: nhung)?(?: duoc)? gi(?: duoc)?"
    r"|(?:toi|minh) (?:nen|can|phai|co the) (?:hoi|nhap|lam) gi"
    r"|(?:dung|su dung) (?:the nao|nhu the nao|ra sao)"
    r"|giup (?:toi|minh)(?: voi)?)"
    r"(?: (?:vay|the|day|nao|a|nhe|nha|nhi|voi))*$"
)
_LAB_WITHOUT_VALUES = re.compile(
    r"^(?:(?:toi|minh) (?:muon|can) |(?:hay|xin|ban|nho) |giup (?:toi|minh) )*"
    r"(?:giai thich|doc|xem|kiem tra|danh gia|phan tich|dien giai)"
    r"(?: giup(?: (?:toi|minh))?)?"
    r"(?: (?:ket qua|chi so))?"
    r" (?:xet nghiem|duong huyet|duong mau|glucose|hba1c|a1c)"
    r"(?: (?:cua|giup|cho) (?:toi|minh)| voi| nhe| nha| duoc khong| di)*$"
    r"|^(?:ket qua|chi so)(?: xet nghiem)? (?:cua|giup) (?:toi|minh)(?: the nao| ra sao| co sao khong)?$"
)


def _clean(message: str) -> str:
    text = re.sub(r"[^\w\s]", " ", normalize_vi(message))
    return re.sub(r"\s+", " ", text).strip()


def classify_guidance(message: str) -> str | None:
    """Match whole messages only, so a real question never gets a canned reply."""
    text = _clean(message)
    if not text or len(text) > 80 or re.search(r"\d", re.sub(r"\b(?:hba1c|a1c)\b", "", text)):
        return None
    if _GREETING_ONLY.match(text):
        return "greeting"
    text = _GREETING_PREFIX.sub("", text)
    if _THANKS.match(text):
        return "thanks"
    if _GOODBYE.match(text):
        return "goodbye"
    if _USAGE_REQUEST.match(text):
        return "usage"
    if _LAB_WITHOUT_VALUES.match(text):
        return "lab_input"
    return None


def guidance_message(kind: str, *, has_profile: bool = False) -> str:
    message = _TEMPLATES[kind]
    if has_profile and kind in {"greeting", "usage"}:
        return f"{message}\n{_PROFILE_NOTE}"
    return message
