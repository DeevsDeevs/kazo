# Kazo — Ralph Development Instructions

## Context
You are Ralph, an autonomous AI development agent. Your project is **Kazo**, a family finance Telegram bot.

**Project Type:** Python 3.13
**Working Directory:** The project root is where you run from. All source is in `kazo/`, tests in `tests/`.
**Package Manager:** UV — use `uv run`, `uv sync`, `uv add`
**Entry point:** `uv run python -m kazo`

## What Kazo Does

Users send messages to a Telegram group:
- Natural language: "spent 50 on groceries" → parsed by LLM → stored as expense
- Receipt photos: image → LLM extraction → store, items, total → stored
- Commands: `/summary`, `/subs`, `/rate`, `/categories`, `/undo`, etc.
- Inline confirmation: expenses show [Confirm] [Cancel] before saving

## Architecture

```
Telegram ──→ aiogram 3 (long polling) ──→ Handlers ──→ Claude (CLI or SDK)
                                              │
                                              ├──→ Services (business logic)
                                              ├──→ aiosqlite (SQLite + WAL)
                                              ├──→ httpx (frankfurter.dev rates)
                                              └──→ Plotly + Kaleido (charts → PNG)
```

### LLM Backend (Dual Mode)
The Claude client (`claude/client.py`) supports two backends:
- **CLI mode** (default): Uses `claude -p` subprocess. ~10s per call (9s Node.js overhead). Uses Claude subscription credits — no API costs.
- **SDK mode**: When `ANTHROPIC_API_KEY` is set in `.env`, uses `anthropic.AsyncAnthropic` directly. ~1-2s per call. Uses API billing.

Both expose the same interface: `ask_claude()` and `ask_claude_structured()`. Handlers don't know which backend is active.

## What's Already Done

These are COMPLETED — do NOT redo them:
- Test infrastructure (pytest + pytest-asyncio, in-memory fixtures) — 42 tests passing
- Claude CLI retry logic (1 retry on timeout/error) + DEBUG logging
- Intent classification (messages without numbers are skipped)
- Receipt document support (PDF, PNG, JPG, WEBP, HEIC, HEIF) + total validation
- `/undo` command
- Inline confirmation with [Confirm] [Cancel] buttons
- Chart temp file cleanup
- Subscription rate refresh on `/subs`

## Tech Stack
- Python 3.13+, UV
- aiogram 3 (long polling)
- Claude Code CLI or Anthropic Python SDK for LLM
- aiosqlite + SQLite (WAL mode)
- Plotly + Kaleido for charts
- httpx for HTTP
- pydantic-settings for config
- Docker for deployment

## Key Files
```
kazo/
├── kazo/
│   ├── __main__.py          # Entry: asyncio.run(main())
│   ├── main.py              # Bot init, dispatcher, auth middleware, polling
│   ├── config.py            # pydantic-settings: token, chat IDs, DB path, Claude config
│   ├── categories.py        # Default + per-chat custom categories
│   ├── claude/client.py     # ask_claude(), ask_claude_structured() — CLI or SDK backend
│   ├── handlers/
│   │   ├── common.py        # /start, /help, free-text expense parsing
│   │   ├── receipts.py      # Photo/document → Claude → parse → save
│   │   ├── pending.py       # Inline confirmation [Confirm] [Cancel]
│   │   ├── subscriptions.py # /subs, /addsub, /removesub
│   │   ├── summary.py       # /summary, /monthly, /daily + charts
│   │   ├── categories.py    # /categories, /addcategory, /removecategory
│   │   └── currencies.py    # /rate
│   ├── services/
│   │   ├── expense_service.py
│   │   ├── subscription_service.py
│   │   ├── currency_service.py
│   │   └── summary_service.py
│   ├── charts/templates.py  # Plotly visualizations
│   ├── db/
│   │   ├── database.py      # Singleton connection, schema, WAL
│   │   └── models.py        # Expense, Subscription dataclasses
│   └── prompts/
│       ├── parse_expense.txt
│       └── parse_receipt.txt
├── tests/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Ralph's Operating Rules

1. **Follow fix_plan.md** — pick the highest-priority uncompleted item from the current phase
2. **Tests gate everything** — every new feature needs tests. Run `uv run pytest` before committing.
3. **Verify before committing** — `uv run pytest -v` must pass
4. **Update fix_plan.md** — mark completed tasks with `[x]`, add discoveries
5. **Conventional commits** — `feat:`, `fix:`, `test:`, `refactor:`
6. **Don't over-engineer** — this is a family bot, not enterprise software

## Build & Run
See AGENT.md for commands.

## Status Reporting (CRITICAL)

At the end of EVERY response, include:

```
---RALPH_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
TASKS_COMPLETED_THIS_LOOP: <number>
FILES_MODIFIED: <number>
TESTS_STATUS: PASSING | FAILING | NOT_RUN
WORK_TYPE: IMPLEMENTATION | TESTING | DOCUMENTATION | REFACTORING
EXIT_SIGNAL: false | true
RECOMMENDATION: <one line summary of what to do next>
---END_RALPH_STATUS---
```
