from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError

from app.safety.classifier import classify_emergency
from app.safety.keyword_rules import (
    contains_medication_dose,
    deterministic_emergency,
    medication_request,
    normalize_vi,
    wound_care_request,
)

EMERGENCY_MESSAGE = (
    "Đây có thể là tình trạng cấp cứu. Hãy gọi 115 ngay hoặc nhờ người bên cạnh gọi. "
    "Không tự lái xe và không tự thay đổi liều insulin/thuốc theo chatbot."
)

CLASSIFIER_TIMEOUT_SECONDS = 1.0
_SAFETY_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="diacare-safety-tier2")


def secondary_safety_heuristic(message: str) -> str:
    """Compatibility name for the independent TF-IDF + Logistic Regression tier."""
    return "EMERGENCY" if classify_emergency(message)["emergency"] else "NORMAL"


def evaluate_safety(
    message: str,
    glucose_value: float | None = None,
    glucose_unit: str | None = None,
    *,
    classifier_timeout_seconds: float = CLASSIFIER_TIMEOUT_SECONDS,
) -> dict:
    # Start the independent classifier first so it runs alongside the cheap
    # deterministic check. If tier 1 flags an emergency, cancel tier 2 without
    # waiting for or using its result.
    try:
        future = _SAFETY_EXECUTOR.submit(secondary_safety_heuristic, message)
    except Exception:
        future = None

    rule_hit = deterministic_emergency(message, glucose_value, glucose_unit)
    if rule_hit:
        if future is not None:
            future.cancel()
        classifier_result = "BYPASSED"
        classifier_status = "bypassed_by_tier1_emergency"
    elif future is None:
        classifier_result = "UNAVAILABLE"
        classifier_status = "unavailable"
    else:
        try:
            classifier_result = future.result(timeout=classifier_timeout_seconds)
            classifier_status = "ready_curated_not_clinically_validated"
        except TimeoutError:
            future.cancel()
            classifier_result = "UNAVAILABLE"
            classifier_status = "timeout"
        except Exception:
            classifier_result = "UNAVAILABLE"
            classifier_status = "unavailable"

    emergency = rule_hit or classifier_result == "EMERGENCY"
    med_review = medication_request(message)
    wound_care = wound_care_request(message)
    unit_ambiguous = glucose_value is not None and glucose_unit not in {"mg/dL", "mmol/L"}
    degraded = classifier_status in {"timeout", "unavailable"}
    level = (
        "EMERGENCY" if emergency else
        "UNKNOWN" if degraded else
        "CLINICAL_REVIEW" if med_review or wound_care else
        "UNIT_AMBIGUOUS" if unit_ambiguous else
        "NORMAL"
    )
    return {
        "level": level,
        "source": "tier1_keyword_rules" if rule_hit else "tier2_tfidf_logistic_regression",
        "rule_signal": rule_hit,
        "classifier_signal": classifier_result,
        "wound_care_request": wound_care,
        "unit_ambiguous": unit_ambiguous,
        "potentially_critical_if_unit_assumed_mg_dl": bool(unit_ambiguous and glucose_value is not None and glucose_value < 54),
        "classifier_status": classifier_status,
        "degraded": degraded,
    }
