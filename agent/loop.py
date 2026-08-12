"""Демо-цикл агента (без живой LLM) + хуки под tool-calling."""

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

_ISSUE_KEY = re.compile(r"\b([A-Za-z]+-\d+)\b", re.IGNORECASE)


@dataclass
class AgentResult:
    status: str  # clarify | confirm | created | listed | commented | deadline_updated | cancelled | error
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
    t = re.split(r"\s+(?:на|до|срок)\s+", t, maxsplit=1, flags=re.IGNORECASE)[0]
    return (t[:120] or "Новая задача").strip()


def _parse_comment_request(text: str) -> Optional[tuple[str, str]]:
    m = re.search(
        r"(?:добавь\s+)?комментари[йя]\s+(?:к\s+)?([A-Za-z]+-\d+)\s*[:\-]?\s*(.+)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).upper(), m.group(2).strip()
    m = re.search(
        r"(?:в|к)\s+([A-Za-z]+-\d+)\s+(?:добавь\s+)?комментари[йя]\s*[:\-]?\s*(.+)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return None


def _parse_deadline_update(text: str) -> Optional[tuple[str, str]]:
    m = re.search(
        r"(?:срок|дедлайн|deadline)\s+(?:у\s+)?([A-Za-z]+-\d+)\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).upper(), m.group(2).strip()
    m = re.search(
        r"(?:перенеси|сдвинь|поставь)\s+срок\s+(?:у\s+)?([A-Za-z]+-\d+)\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).upper(), m.group(2).strip()
    key_m = _ISSUE_KEY.search(text)
    if key_m and any(w in text.lower() for w in ("срок", "дедлайн", "до ", "на завтра", "на пятниц")):
        return key_m.group(1).upper(), text
    return None


class TrackerAgent:
    def __init__(self, *, dry_run: bool = True, ask_clarify: bool = True, require_confirm: bool = True):
        self.dry_run = dry_run
        self.ask_clarify = ask_clarify
        self.require_confirm = require_confirm
        self.draft = TaskDraft()
        self.trace: List[Dict[str, Any]] = []
        self.awaiting_assignee_change = False

    def reset(self) -> None:
        self.draft = TaskDraft()
        self.trace = []
        self.awaiting_assignee_change = False

    def _run_tool(self, name: str, **kwargs: Any) -> dict:
        handlers = get_tool_handlers(self.draft, dry_run=self.dry_run)
        if name not in handlers:
            out = {"ok": False, "error": f"unknown_tool:{name}"}
        else:
            out = handlers[name](**kwargs)
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

        if self.awaiting_assignee_change:
            self.awaiting_assignee_change = False
            return self.apply_assignee(text)

        # ответ на уточнение исполнителя — короткое имя
        if (
            self.draft.clarification
            and self.draft.title
            and not self.draft.assignee_login
            and len(text.split()) <= 4
            and not any(x in text.lower() for x in ("создай", "задач", "комментар", "срок"))
        ):
            self.draft.clarification = ""
            if text.lower() in ("без исполнителя", "без", "-"):
                return self._show_confirm()
            return self.apply_assignee(text)

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

        comment = _parse_comment_request(text)
        if comment:
            issue_key, body = comment
            out = self._run_tool("add_comment", issue_key=issue_key, text=body)
            if not out.get("ok"):
                return AgentResult(
                    status="error",
                    message=str(out.get("error") or "не удалось добавить комментарий"),
                    draft=self.draft.to_dict(),
                    tool_trace=list(self.trace),
                )
            return AgentResult(
                status="commented",
                message=out.get("message") or f"Комментарий к {issue_key} добавлен",
                draft=self.draft.to_dict(),
                tool_trace=list(self.trace),
            )

        deadline_upd = _parse_deadline_update(text)
        if deadline_upd:
            issue_key, deadline_text = deadline_upd
            out = self._run_tool("update_deadline", issue_key=issue_key, deadline_text=deadline_text)
            if not out.get("ok"):
                return AgentResult(
                    status="error",
                    message="Не разобрала срок. Пример: «срок DEMO-10 на завтра»",
                    draft=self.draft.to_dict(),
                    tool_trace=list(self.trace),
                )
            return AgentResult(
                status="deadline_updated",
                message=out.get("message") or f"Срок {issue_key} обновлён",
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
            return self._show_confirm()

        created = self._run_tool("create_task", confirmed=True)
        return AgentResult(
            status="created",
            message=f"Создано: {created.get('issue_key')} ({created.get('url')})",
            draft=self.draft.to_dict(),
            tool_trace=list(self.trace),
        )

    def _show_confirm(self) -> AgentResult:
        out = self._run_tool("confirm_draft")
        card = out.get("card") or {}
        msg = (
            "Проверьте задачу перед созданием:\n\n"
            f"• {card.get('title')}\n"
            f"• {card.get('description')}\n"
            f"• Исполнитель: {card.get('assignee')}\n"
            f"• Срок: {card.get('deadline')}"
        )
        return AgentResult(
            status="confirm",
            message=msg,
            draft=self.draft.to_dict(),
            tool_trace=list(self.trace),
            buttons=list(out.get("buttons") or []),
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
            message=f"Задача создана: {created.get('issue_key')}\n{created.get('url')}",
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
        self.draft.clarification = ""
        if self.require_confirm and self.draft.title:
            return self._show_confirm()
        return self.handle_user_text(self.draft.description or self.draft.title or hint)

    def request_assignee_change(self) -> AgentResult:
        self.awaiting_assignee_change = True
        return AgentResult(
            status="clarify",
            message="На кого переназначить? Напишите фамилию.",
            draft=self.draft.to_dict(),
            tool_trace=list(self.trace),
        )

    def cancel(self) -> AgentResult:
        self.reset()
        return AgentResult(
            status="cancelled",
            message="Отменено. Черновик сброшен.",
            draft=self.draft.to_dict(),
            tool_trace=list(self.trace),
        )
