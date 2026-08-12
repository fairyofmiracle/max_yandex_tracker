# Architecture

## Confirmation gate (required)

```mermaid
flowchart TD
  A[User text or voice] --> B[STT GigaAM on-prem]
  B --> C[Agent tools / LLM]
  C --> D{Slots enough?}
  D -->|no| E[ask_clarification]
  E --> A
  D -->|yes| F[confirm_draft card]
  F --> G{User confirms?}
  G -->|yes| H[create_task Tracker API]
  G -->|edit assignee| I[search_assignee]
  I --> F
  G -->|cancel| J[Stop]
```

Production bot already has this UX. This repo keeps the same contract in the tool layer: `create_task` fails unless confirmed.

## Trust boundaries

| Zone | Components |
|------|------------|
| Messenger | MAX webhook (auth via secret) |
| Agent runtime | FastAPI, session, tools |
| Inference (LAN) | GigaAM STT, local LLM |
| Systems of record | Yandex Tracker API |

Audio and task text are processed inside the perimeter; they are not sent to public cloud STT/LLM APIs.

## Extending tools

Add a handler in `tools/tracker_tools.py`, register it in `TOOL_SPECS` and `get_tool_handlers`, cover with a unit test in `tests/`.
