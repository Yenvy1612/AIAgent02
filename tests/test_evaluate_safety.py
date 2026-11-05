from __future__ import annotations

import pytest

from scripts import evaluate_safety


def test_normal_question_summary_reports_false_alarm_rate_and_cases():
    result = evaluate_safety.summarize_normal_questions([
        {"id": "N01", "message": "Câu hỏi bình thường", "tier2_emergency": False, "combined_level": "NORMAL"},
        {"id": "N02", "message": "Câu bị báo nhầm", "tier2_emergency": True, "combined_level": "EMERGENCY"},
    ])

    assert result["case_count"] == 2
    assert result["tier2_false_positive_count"] == 1
    assert result["tier2_false_positive_rate"] == 0.5
    assert result["false_alarm_count"] == 1
    assert result["false_alarm_rate"] == 0.5
    assert result["false_alarms"] == [{"id": "N02", "message": "Câu bị báo nhầm"}]


def test_held_out_normal_questions_reject_training_duplicates():
    with pytest.raises(ValueError, match="overlap"):
        evaluate_safety.validate_no_training_overlap(
            [{"id": "N01", "message": "ĐÁI THÁO ĐƯỜNG TÍP 2?", "emergency": False}],
            [{"text": "đái tháo đường típ 2?"}],
        )
