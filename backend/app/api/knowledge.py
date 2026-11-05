from __future__ import annotations

from fastapi import APIRouter

from app.agent.tools import search_kb
from app.api.schemas import SearchInput

router = APIRouter(prefix="/api/v1")


@router.post("/knowledge/search")
def knowledge_search(data: SearchInput):
    return search_kb(data.query, data.topic, data.top_k)
