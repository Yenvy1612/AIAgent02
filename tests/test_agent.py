from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.chat import chat  # noqa: E402
from app.api.schemas import ChatInput  # noqa: E402
from app.agent.graph import _route_node  # noqa: E402


def test_sadd_ml_rag_demo_routes_history_model_and_knowledge():
    message = "Hãy phân tích hồ sơ DEMO-01 theo mô hình và giải thích các yếu tố liên quan."
    route = _route_node({"message": message, "trace": []})
    assert [call["name"] for call in route["calls"]] == ["get_history", "predict_risk", "search_kb"]


def test_switching_profiles_uses_only_the_profile_selected_for_each_request():
    observed = []

    def fake_run(message, profile_id, db):
        observed.append(profile_id)
        return {"status": "OK", "answer": f"fresh result for {profile_id}"}

    with (
        patch("app.api.chat.evaluate_safety", return_value={"level": "NORMAL"}),
        patch("app.api.chat.list_profiles", return_value=[{"id": "DEMO-01"}, {"id": "DEMO-02"}]),
        patch("app.api.chat.run_agent", side_effect=fake_run),
    ):
        first = chat(ChatInput(message="Tính BMI của hồ sơ này", demo_profile_id="DEMO-01"), db=None)
        second = chat(ChatInput(message="Tính BMI của hồ sơ này", demo_profile_id="DEMO-02"), db=None)
    assert observed == ["DEMO-01", "DEMO-02"]
    assert first["profile_type"] == second["profile_type"] == "synthetic"
    assert first["answer"] != second["answer"]


def test_nonexistent_demo_profile_returns_profile_not_found():
    with (
        patch("app.api.chat.evaluate_safety", return_value={"level": "NORMAL"}),
        patch("app.api.chat.list_profiles", return_value=[{"id": "DEMO-01"}]),
    ):
        with pytest.raises(HTTPException) as raised:
            chat(ChatInput(message="Tính BMI", demo_profile_id="DEMO-99"), db=None)
    assert raised.value.status_code == 404
    assert raised.value.detail == {"code": "PROFILE_NOT_FOUND", "profile_id": "DEMO-99"}
