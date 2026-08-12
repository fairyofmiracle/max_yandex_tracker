#!/usr/bin/env python3
"""Placeholder: generate demo assignee aliases (no production employee dump)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "assignee_org_aliases.example.json"

EXAMPLE = {
    "version": 1,
    "hint_to_login": {
        "иванов": "ivanov",
        "иванова": "ivanov",
        "саша": "alexandrov",
    },
    "people": [
        {"login": "ivanov", "display": "Иванов И.И."},
        {"login": "alexandrov", "display": "Александров А.А."},
    ],
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(EXAMPLE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
