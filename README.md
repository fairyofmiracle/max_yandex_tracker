# MAX Tracker Agent

Онпрем-агент: создаёт задачи в Яндекс Трекере из MAX (текст или голос).

Не FAQ-бот: разбирает запрос, дергает тулы, показывает карточку подтверждения и только потом создаёт задачу.

```text
MAX (текст/голос)
  → STT GigaAM (on-prem)
  → агент (локальная LLM + tools)
  → карточка подтверждения
  → Yandex Tracker API
```

STT и LLM работают внутри периметра. Задача уходит в Трекер только после явного «да».

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

pytest -q
python -m bot.demo_cli "Создай задачу подготовить отчёт на Иванова до пятницы" --confirm
```

HTTP-демо (без токена MAX):

```bash
uvicorn bot.main:app --host 127.0.0.1 --port 8013
curl -s http://127.0.0.1:8013/ping
```

## Тулы

| Tool | Зачем |
|------|--------|
| `search_assignee` | Имя / уменьшительное → логин |
| `parse_deadline` | Дедлайны из русских фраз |
| `draft_task` | Поля задачи |
| `ask_clarification` | Уточнить, если чего-то не хватает |
| `confirm_draft` | Карточка подтверждения (без сайд-эффектов) |
| `create_task` | Создать в Трекере только после confirm |
| `list_my_tasks` | Список открытых задач |
| `add_comment` | Комментарий к задаче |
| `update_deadline` | Обновить срок |

## STT: GigaAM

Распознавание через [GigaAM](https://github.com/salute-developers/GigaAM) on-prem.

Если весов нет, можно `STT_ALLOW_STUB=1` — для локальных прогонов и CI.

## LLM

Локальный OpenAI-compatible endpoint (например Gemma через llama-server). В `.env`:

```env
LLM_API_BASE_URL=http://127.0.0.1:10000
LLM_CHAT_URL=http://127.0.0.1:10000/v1/chat/completions
LLM_MODEL=gemma-local
```

## Структура

```text
agent/   цикл агента, system prompt
stt/     GigaAM + stub
tools/   тулы Трекера / диалога
bot/     FastAPI + CLI
docs/    архитектура, roadmap
tests/   тесты
```

## Безопасность

`.env` и прод-токены в репозиторий не кладём. Подробности — [SECURITY.md](SECURITY.md).

## Документация

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)

## License

MIT — [LICENSE](LICENSE).
