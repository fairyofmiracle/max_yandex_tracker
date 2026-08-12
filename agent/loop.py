"""Deterministic agent loop (works without live LLM) + optional LLM hooks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tools.tracker_tools import TaskDraft, get_tool_handlers

logger = logging.getLogger("max_tracker_agent.agent")

SYSTEM_PROMPT = """Ты ИИ-агент постановки задач в Яндекс Трекер.
Работай только через tools. Данные остаются во внутреннем контуре.
Обязательно: перед create_task вызови confirm_draft и дождись подтверждения пользователя.
Если не хватает исполнителя или сути — ask_clarification.
Не выдумывай логины сотрудников: только search_assignee.
Отвечай пользователю по-русски кратко.
"""


@dataclass
class AgentResult:
    status: str  # clarify | confirm | created | listed | error
    message: str
    draft: Dict[str, Any] = field(default_factory=dict)
    tool_trace: List[Dict[str, Any]] = field(default_factory=list)
    buttons: List[str] = field(default_factory=list)


def _guess_assignee(text: str) -> str:
    m = re.search(
        r"(?:на|для|исполнител[ьяю]?)\s+([А-ЯЁа-яёA-Za-z]{3,})",
        text,
        re.IGNORECASE,
    )
    return (m.group(1) if m else "").strip()


def _guess_title(text: str) -> str:
    t = text.strip()
    t = re.sub(
        r"^(создай|поставь|нужно|надо)\s+(задачу\s*)?(:|\s)?",
        "",
        t,
        flags=re.IGNORECASE,
    ).strip()
    # drop assignee / deadline tail for short title
    t = re.split(r"\s+(?:на|до|срок)\s+", t, maxsplit=1, flags=re.IGNORECASE)[0]
    return (t[:120] or "Новая задача").strip()


class TrackerAgent:
    """
    v2 agent:
    - multi-step tools
    - confirmation before create (same UX as prod)
    - optional clarify
    """

    def __init__(self, *, dry_run: bool = True, ask_clarify: bool = True, require_confirm: bool = True):
        self.dry_run = dry_run
        self.ask_clarify = ask_clarify
        self.require_confirm = require_confirm
        self.draft = TaskDraft()
        self.trace: List[Dict[str, Any]] = []

    def _run_tool(self, name: str, **kwargs: Any) -> dict:
        handlers = get_tool_handlers(self.draft, dry_run=self.dry_run)
        if name not in handlers:
            out = {"ok": False, "error": f"unknown_tool:{name}"}
        else:
            out = handlers[name](**kwargs)
        # sync draft from tool output when present
        if isinstance(out.get("draft"), dict):
            d = out["draft"]
            for k, v in d.items():
                if hasattr(self.draft, k) and v is not None:
                    setattr(self.draft, k, v)
        self.trace.append({"tool": name, "args": kwargs, "result": out})
        return out

    def handle_user_text(self, text: str) -> AgentResult:
        text = (text or "").strip()
        if not text:
            return AgentResult(status="error", message="Пустое сообщение", tool_trace=self.trace)

        low = text.lower()
        if any(x in low for x in ("мои задачи", "список задач", "что у меня")):
            out = self._run_tool("list_my_tasks", limit=5)
            lines = [f"• {t['key']}: {t['summary']}" for t in out.get("tasks") or []]
            return AgentResult(
                status="listed",
                message="Открытые задачи:\n" + ("\n".join(lines) or "пусто"),
                draft=self.draft.to_dict(),
                tool_trace=list(self.trace),
            )

        title = _guess_title(text)
        assignee_hint = _guess_assignee(text)
        self._run_tool(
            "draft_task",
            title=title,
            description=text,
            assignee_hint=assignee_hint,
            deadline_text=text,
        )

        if self.ask_clarify and not self.draft.assignee_login and not assignee_hint:
            out = self._run_tool(
                "ask_clarification",
                question="На кого поставить задачу? Напишите фамилию или «без исполнителя».",
            )
            return AgentResult(
                status="clarify",
                message=out.get("question") or "Уточните исполнителя",
                draft=self.draft.to_dict(),
                tool_trace=list(self.trace),
            )

        if self.require_confirm:
            out = self._run_tool("confirm_draft")
            card = out.get("card") or {}
            msg = (
                "📋 Проверьте задачу перед созданием:\n\n"
                f"📌 {card.get('title')}\n"
                f"📝 {card.get('description')}\n"
                f"👤 Исполнитель: {card.get('assignee')}\n"
                f"⏳ Срок: {card.get('deadline')}"
            )
            return AgentResult(
                status="confirm",
                message=msg,
                draft=self.draft.to_dict(),
                tool_trace=list(self.trace),
                buttons=list(out.get("buttons") or []),
            )

        # Only if confirm disabled (not recommended)
        created = self._run_tool("create_task", confirmed=True)
        return AgentResult(
            status="created",
            message=f"Создано: {created.get('issue_key')} ({created.get('url')})",
            draft=self.draft.to_dict(),
            tool_trace=list(self.trace),
        )

    def confirm_create(self) -> AgentResult:
        created = self._run_tool("create_task", confirmed=True)
        if not created.get("ok"):
            return AgentResult(
                status="error",
                message=str(created.get("error") or "не удалось создать"),
                draft=self.draft.to_dict(),
                tool_trace=list(self.trace),
            )
        return AgentResult(
            status="created",
            message=f"✅ Задача создана: {created.get('issue_key')}\n{created.get('url')}",
            draft=self.draft.to_dict(),
            tool_trace=list(self.trace),
        )

    def apply_assignee(self, hint: str) -> AgentResult:
        found = self._run_tool("search_assignee", hint=hint)
        if found.get("ok"):
            self.draft.assignee_login = found["login"]
            self.draft.assignee_display = found["display"]
            self.draft.assignee_hint = hint
        else:
            self.draft.assignee_hint = hint
            self.draft.assignee_login = ""
            self.draft.assignee_display = ""
        return self.handle_user_text(self.draft.description or self.draft.title or hint)
