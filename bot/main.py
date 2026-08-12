"""FastAPI: демо-чат без секретов. Webhook MAX — отдельно, из прода."""

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

app = FastAPI(title="MAX Tracker Agent", version="0.1.0")

# сессии в памяти; в проде — Redis
_SESSIONS: dict[str, TrackerAgent] = {}


class ChatIn(BaseModel):
    user_id: str = "demo"
    text: str = ""
    action: str | None = None  # confirm_create | change_assignee | cancel


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
    return {"status": "ok", "service": "max_tracker_agent"}


@app.post("/demo/chat", response_model=ChatOut)
async def demo_chat(body: ChatIn):
    """Локальное демо — без реальных MAX/Трекера."""
    agent = _agent_for(body.user_id)
    action = (body.action or "").strip().lower()

    if action == "confirm_create":
        result = agent.confirm_create()
    elif action == "change_assignee":
        hint = (body.text or "").strip()
        result = agent.apply_assignee(hint) if hint else agent.request_assignee_change()
    elif action == "cancel":
        result = agent.cancel()
    else:
        if not (body.text or "").strip():
            return ChatOut(status="error", message="Пустое сообщение")
        result = agent.handle_user_text(body.text)

    return ChatOut(
        status=result.status,
        message=result.message,
        buttons=result.buttons,
        draft=result.draft,
    )
