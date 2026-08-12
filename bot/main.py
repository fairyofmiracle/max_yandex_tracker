"""Minimal FastAPI skeleton — no secrets required to import/start in dry mode."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import TrackerAgent
from bot.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("max_tracker_agent")

app = FastAPI(title="MAX Tracker Agent v2", version="0.1.0")

# In-memory sessions for scaffold demos (replace with Redis/DB in prod port)
_SESSIONS: dict[str, TrackerAgent] = {}


class ChatIn(BaseModel):
    user_id: str = "demo"
    text: str = Field(..., min_length=1)
    action: str | None = None  # confirm_create | change_assignee


class ChatOut(BaseModel):
    status: str
    message: str
    buttons: list[str] = []
    draft: dict = {}


def _agent_for(user_id: str) -> TrackerAgent:
    if user_id not in _SESSIONS:
        s = get_settings()
        _SESSIONS[user_id] = TrackerAgent(
            dry_run=True,
            ask_clarify=s.agent_ask_clarify,
            require_confirm=s.agent_require_confirm,
        )
    return _SESSIONS[user_id]


@app.get("/ping")
async def ping():
    return {"status": "ok", "service": "max_tracker_agent_v2"}


@app.post("/demo/chat", response_model=ChatOut)
async def demo_chat(body: ChatIn):
    """Local demo endpoint — does not call real MAX/Tracker."""
    agent = _agent_for(body.user_id)
    if body.action == "confirm_create":
        result = agent.confirm_create()
    else:
        result = agent.handle_user_text(body.text)
    return ChatOut(
        status=result.status,
        message=result.message,
        buttons=result.buttons,
        draft=result.draft,
    )


# Placeholder: real MAX webhook will be ported from max_yandex_tracker carefully
# @app.post("/webhook")
# async def max_webhook(...): ...
