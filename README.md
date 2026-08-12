# MAX Tracker Agent

On-premise **AI agent** for creating Yandex Tracker issues from MAX messenger (text or voice).

Not a FAQ chatbot: the agent understands the request, calls tools, shows a confirmation card, then creates the task in Tracker.

```text
MAX (text/voice)
  → STT GigaAM (Sber, on-prem)
  → Agent loop (local LLM + tools)
  → Confirmation card
  → Yandex Tracker API
```

## Why this design

| Principle | Implementation |
|-----------|----------------|
| Data stays in perimeter | STT + LLM run on-prem; no public cloud inference |
| Agent, not templates | Tool-calling: draft → clarify → confirm → create |
| Human-in-the-loop | Task is created only after explicit confirmation |
| Safe to share | This repo has **no secrets**, no production employees, dry-run demos |

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

pytest -q
python -m bot.demo_cli "Создай задачу подготовить отчёт на Иванова до пятницы" --confirm
```

Demo HTTP API (no MAX token required):

```bash
uvicorn bot.main:app --host 127.0.0.1 --port 8013
curl -s http://127.0.0.1:8013/ping
```

## Agent tools

| Tool | Role |
|------|------|
| `search_assignee` | Resolve name / diminutive via org aliases |
| `parse_deadline` | Extract deadlines from Russian phrases |
| `draft_task` | Build issue fields |
| `ask_clarification` | Ask when assignee/intent is unclear |
| `confirm_draft` | Show confirmation card (**no side effects**) |
| `create_task` | Create in Tracker **only if confirmed** |
| `list_my_tasks` | List open issues in natural language |

## STT: GigaAM (Sber)

Speech recognition uses open-source [GigaAM](https://github.com/salute-developers/GigaAM) deployed on-prem.

```bash
# on GPU host
git clone https://github.com/salute-developers/GigaAM.git
cd GigaAM && pip install -e ".[torch]"
```

Without weights, the scaffold uses a safe stub (`STT_ALLOW_STUB=1`) so demos and CI still run.

## LLM

Local OpenAI-compatible endpoint (e.g. Gemma via llama-server). Configure in `.env`:

```env
LLM_API_BASE_URL=http://127.0.0.1:10000
LLM_CHAT_URL=http://127.0.0.1:10000/v1/chat/completions
LLM_MODEL=gemma-local
```

## Repository layout

```text
agent/     agent loop, system prompt
stt/       GigaAM adapter + stub
tools/     Tracker/dialog tools
bot/       FastAPI skeleton + CLI demo
docs/      architecture, roadmap, demo script
tests/     unit tests
```

## Security

- Never commit `.env`
- Production tokens, org directories, and internal URLs stay in a private contour
- This public scaffold is intentionally dry-run by default

See [SECURITY.md](SECURITY.md).

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Demo recording tips](docs/DEMO.md)

## License

MIT — see [LICENSE](LICENSE).
