"""Agent tools: each returns a JSON-serialisable dict for the LLM loop."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional


@dataclass
class TaskDraft:
    title: str = ""
    description: str = ""
    assignee_hint: str = ""
    assignee_login: str = ""
    assignee_display: str = ""
    deadline_iso: str = ""
    queue_key: str = ""
    confirmed: bool = False
    created_issue_key: str = ""
    clarification: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --- demo org aliases (no real employees) ---
DEMO_ALIASES: Dict[str, tuple[str, str]] = {
    "иванов": ("ivanov", "Иванов И.И."),
    "иванова": ("ivanov", "Иванов И.И."),
    "саша": ("alexandrov", "Александров А.А."),
    "александр": ("alexandrov", "Александров А.А."),
    "петров": ("petrov", "Петров П.П."),
}


def tool_search_assignee(hint: str, **_: Any) -> dict:
    h = (hint or "").strip().lower()
    if not h:
        return {"ok": False, "error": "empty_hint", "matches": []}
    if h in DEMO_ALIASES:
        login, display = DEMO_ALIASES[h]
        return {
            "ok": True,
            "login": login,
            "display": display,
            "matches": [{"login": login, "display": display}],
        }
    # diminutive / soft match
    for key, (login, display) in DEMO_ALIASES.items():
        if key.startswith(h) or h.startswith(key):
            return {
                "ok": True,
                "login": login,
                "display": display,
                "matches": [{"login": login, "display": display}],
            }
    return {"ok": False, "error": "not_found", "hint": hint, "matches": []}


def tool_parse_deadline(text: str, *, today: Optional[date] = None, **_: Any) -> dict:
    today = today or date.today()
    raw = (text or "").lower()
    iso = ""
    if "сегодня" in raw:
        iso = today.isoformat()
    elif "завтра" in raw:
        iso = (today + timedelta(days=1)).isoformat()
    elif "пятниц" in raw:
        # next Friday
        delta = (4 - today.weekday()) % 7
        if delta == 0:
            delta = 7
        iso = (today + timedelta(days=delta)).isoformat()
    elif "недел" in raw:
        iso = (today + timedelta(days=7)).isoformat()
    else:
        m = re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", raw)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
            year = today.year if not y else (2000 + int(y) if len(y) == 2 else int(y))
            try:
                iso = date(year, mo, d).isoformat()
            except ValueError:
                iso = ""
    return {"ok": bool(iso), "deadline_iso": iso, "source": text}


def tool_draft_task(
    title: str,
    description: str = "",
    assignee_hint: str = "",
    deadline_text: str = "",
    draft: Optional[TaskDraft] = None,
    **_: Any,
) -> dict:
    draft = draft or TaskDraft()
    draft.title = (title or "").strip()[:200] or draft.title
    draft.description = (description or title or draft.description).strip()
    if assignee_hint:
        draft.assignee_hint = assignee_hint.strip()
        found = tool_search_assignee(assignee_hint)
        if found.get("ok"):
            draft.assignee_login = found["login"]
            draft.assignee_display = found["display"]
    if deadline_text:
        dl = tool_parse_deadline(deadline_text)
        if dl.get("ok"):
            draft.deadline_iso = dl["deadline_iso"]
    draft.confirmed = False
    return {"ok": True, "draft": draft.to_dict()}


def tool_ask_clarification(question: str, draft: Optional[TaskDraft] = None, **_: Any) -> dict:
    draft = draft or TaskDraft()
    q = (question or "").strip()
    draft.clarification = q
    return {"ok": True, "action": "ask_user", "question": q, "draft": draft.to_dict()}


def tool_confirm_draft(draft: Optional[TaskDraft] = None, **_: Any) -> dict:
    """Show confirmation card — does NOT create the task yet."""
    draft = draft or TaskDraft()
    missing: List[str] = []
    if not draft.title:
        missing.append("title")
    card = {
        "title": draft.title or "(без названия)",
        "description": draft.description,
        "assignee": draft.assignee_display or draft.assignee_hint or "не указан",
        "deadline": draft.deadline_iso or "не указан",
    }
    return {
        "ok": True,
        "action": "show_confirm_card",
        "message": "Проверьте задачу перед созданием",
        "card": card,
        "missing": missing,
        "buttons": ["confirm_create", "change_assignee", "cancel"],
        "draft": draft.to_dict(),
    }


def tool_create_task(
    *,
    confirmed: bool = False,
    draft: Optional[TaskDraft] = None,
    dry_run: bool = True,
    **_: Any,
) -> dict:
    draft = draft or TaskDraft()
    if not confirmed and not draft.confirmed:
        return {
            "ok": False,
            "error": "not_confirmed",
            "hint": "Сначала confirm_draft / кнопка «Создать задачу»",
        }
    if not draft.title:
        return {"ok": False, "error": "empty_title"}
    draft.confirmed = True
    # dry-run issue key
    key = "DEMO-1" if dry_run else "QUEUE-0"
    draft.created_issue_key = key
    return {
        "ok": True,
        "issue_key": key,
        "url": f"https://tracker.yandex.ru/{key}",
        "dry_run": dry_run,
        "draft": draft.to_dict(),
    }


def tool_list_my_tasks(limit: int = 5, **_: Any) -> dict:
    demo = [
        {"key": "DEMO-10", "summary": "Подготовить отчёт", "status": "open"},
        {"key": "DEMO-11", "summary": "Согласовать регламент", "status": "open"},
    ]
    return {"ok": True, "tasks": demo[: max(1, int(limit))]}


TOOL_SPECS: List[dict] = [
    {
        "name": "search_assignee",
        "description": "Найти исполнителя по фамилии/имени/уменьшительному в орг-словаре",
        "parameters": {"hint": "string"},
    },
    {
        "name": "parse_deadline",
        "description": "Извлечь срок из русской фразы",
        "parameters": {"text": "string"},
    },
    {
        "name": "draft_task",
        "description": "Собрать/обновить черновик задачи",
        "parameters": {
            "title": "string",
            "description": "string",
            "assignee_hint": "string",
            "deadline_text": "string",
        },
    },
    {
        "name": "ask_clarification",
        "description": "Задать пользователю уточняющий вопрос",
        "parameters": {"question": "string"},
    },
    {
        "name": "confirm_draft",
        "description": "Показать карточку подтверждения ДО создания в Трекере",
        "parameters": {},
    },
    {
        "name": "create_task",
        "description": "Создать задачу в Трекере только после подтверждения",
        "parameters": {"confirmed": "bool"},
    },
    {
        "name": "list_my_tasks",
        "description": "Список открытых задач пользователя",
        "parameters": {"limit": "int"},
    },
]


def get_tool_handlers(draft: TaskDraft, dry_run: bool = True) -> Dict[str, Callable[..., dict]]:
    def _wrap(fn: Callable[..., dict]) -> Callable[..., dict]:
        def inner(**kwargs: Any) -> dict:
            return fn(draft=draft, dry_run=dry_run, **kwargs)

        return inner

    return {
        "search_assignee": tool_search_assignee,
        "parse_deadline": tool_parse_deadline,
        "draft_task": _wrap(tool_draft_task),
        "ask_clarification": _wrap(tool_ask_clarification),
        "confirm_draft": _wrap(tool_confirm_draft),
        "create_task": _wrap(tool_create_task),
        "list_my_tasks": tool_list_my_tasks,
    }
