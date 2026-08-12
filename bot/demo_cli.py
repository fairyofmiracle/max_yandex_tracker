"""Dry-run CLI to try the agent without MAX/Tracker credentials."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# allow running as `python -m bot.demo_cli` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import TrackerAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="MAX Tracker Agent v2 demo (dry-run)")
    parser.add_argument(
        "text",
        nargs="?",
        default="Создай задачу подготовить отчёт на Иванова до пятницы",
        help="User utterance",
    )
    parser.add_argument("--confirm", action="store_true", help="Also press confirm after card")
    parser.add_argument("--json", action="store_true", help="Print JSON trace")
    args = parser.parse_args()

    agent = TrackerAgent(dry_run=True, ask_clarify=True, require_confirm=True)
    result = agent.handle_user_text(args.text)
    print(result.message)
    if result.buttons:
        print("Кнопки:", ", ".join(result.buttons))
    if args.confirm and result.status == "confirm":
        print("---")
        created = agent.confirm_create()
        print(created.message)
        result = created
    if args.json:
        print(json.dumps({"status": result.status, "draft": result.draft, "trace": result.tool_trace}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
