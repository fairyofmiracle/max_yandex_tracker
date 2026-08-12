import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.loop import TrackerAgent
from tools.tracker_tools import (
    TaskDraft,
    load_org_aliases,
    tool_add_comment,
    tool_create_task,
    tool_parse_deadline,
    tool_search_assignee,
    tool_update_deadline,
)


def test_search_assignee_ivanov():
    out = tool_search_assignee("Иванова")
    assert out["ok"] is True
    assert out["login"] == "ivanov"


def test_load_org_aliases_not_empty():
    aliases = load_org_aliases()
    assert "иванов" in aliases


def test_parse_deadline_friday():
    out = tool_parse_deadline("до пятницы")
    assert out["ok"] is True
    assert out["deadline_iso"]


def test_create_requires_confirm():
    draft = TaskDraft(title="Тест")
    out = tool_create_task(confirmed=False, draft=draft, dry_run=True)
    assert out["ok"] is False
    assert out["error"] == "not_confirmed"


def test_agent_shows_confirm_card():
    agent = TrackerAgent(dry_run=True, ask_clarify=False, require_confirm=True)
    result = agent.handle_user_text("Создай задачу подготовить отчёт на Иванова до пятницы")
    assert result.status == "confirm"
    assert "Проверьте задачу" in result.message
    assert "confirm_create" in result.buttons


def test_agent_confirm_creates():
    agent = TrackerAgent(dry_run=True, ask_clarify=False, require_confirm=True)
    agent.handle_user_text("Подготовить отчёт на Иванова")
    created = agent.confirm_create()
    assert created.status == "created"
    assert "DEMO-1" in created.message


def test_agent_clarify_without_assignee():
    agent = TrackerAgent(dry_run=True, ask_clarify=True, require_confirm=True)
    result = agent.handle_user_text("Нужно подготовить сводку по отчёту")
    assert result.status == "clarify"


def test_agent_add_comment():
    agent = TrackerAgent(dry_run=True)
    result = agent.handle_user_text("Добавь комментарий к DEMO-10: ждём данные")
    assert result.status == "commented"
    assert "DEMO-10" in result.message


def test_tool_add_comment_empty():
    out = tool_add_comment("DEMO-10", "", dry_run=True)
    assert out["ok"] is False


def test_agent_update_deadline():
    agent = TrackerAgent(dry_run=True)
    result = agent.handle_user_text("Срок DEMO-10 на завтра")
    assert result.status == "deadline_updated"
    assert "DEMO-10" in result.message


def test_tool_update_deadline():
    out = tool_update_deadline("DEMO-11", "до пятницы", dry_run=True)
    assert out["ok"] is True
    assert out["deadline_iso"]


def test_agent_cancel():
    agent = TrackerAgent(dry_run=True, ask_clarify=False)
    agent.handle_user_text("Подготовить отчёт на Иванова")
    cancelled = agent.cancel()
    assert cancelled.status == "cancelled"
    assert agent.draft.title == ""


def test_agent_change_assignee():
    agent = TrackerAgent(dry_run=True, ask_clarify=False, require_confirm=True)
    agent.handle_user_text("Подготовить отчёт на Иванова")
    result = agent.apply_assignee("Петров")
    assert result.status == "confirm"
    assert result.draft["assignee_login"] == "petrov"
