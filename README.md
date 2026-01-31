# Kazo

Family finance tracking through Telegram. Send a message, get a ledger entry. Photograph a receipt, get it parsed. Ask a question, get an answer with a chart.

Built on aiogram 3, SQLite, and Claude Code CLI as the language model backbone.

## Architecture

```
Telegram → aiogram 3 (long polling) → Handlers → Claude CLI (subprocess)
                                          ├── Services (business logic)
                                          ├── aiosqlite (SQLite + WAL)
                                          ├── httpx (frankfurter.dev rates)
                                          └── Plotly + Kaleido (charts → PNG)
```

All LLM calls go through Claude Code CLI as a subprocess — not the Python SDK. This gives structured JSON output via `--json-schema`, tool use for receipt reading, and zero SDK dependency.

## Commands

| Command | What it does |
|---------|-------------|
| `/start` | Bot intro |
| `/help` | Command reference |
| `/undo` | Delete last expense |
| `/summary` | This month by category + chart |
| `/monthly` | 6-month trend + chart |
| `/daily` | Last 30 days + chart |
| `/subs` | List active subscriptions (refreshes rates) |
| `/addsub Name Amount Currency [frequency]` | Add subscription |
| `/removesub Name` | Deactivate subscription |
| `/categories` | List all categories |
| `/addcategory Name` | Add custom category |
| `/removecategory Name` | Remove custom category |
| `/rate [Currency]` | EUR exchange rate |

**Free text**: Send any message with a number and Kazo parses it as an expense.
**Photos/Documents**: Send a receipt image (JPG, PNG, WEBP, HEIC) or PDF and Kazo extracts the line items.

## Setup

### Prerequisites

- Python 3.13+
- [UV](https://docs.astral.sh/uv/) package manager
- Claude Code CLI (`npx @anthropic-ai/claude-code`)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Install

```bash
cd kazo
uv sync
```

### Configure

Copy `.env.example` to `.env` and fill in:

```bash
TELEGRAM_BOT_TOKEN=your-token-here
ALLOWED_CHAT_IDS=123456789,987654321   # optional, restricts access
DB_PATH=kazo.db                         # default
CLAUDE_MODEL=sonnet                     # default
CLAUDE_TIMEOUT=60                       # seconds, default
```

### Run

```bash
uv run python -m kazo
```

### Docker

```bash
docker compose up -d
```

## Tests

```bash
cd kazo
uv run pytest
```

42 tests covering services, database, Claude CLI client, receipt handlers, and categories.

## Project Structure

```
kazo/
├── kazo/
│   ├── main.py              # Bot init, polling, auth middleware
│   ├── config.py            # Pydantic settings from env
│   ├── categories.py        # 14 defaults + per-chat custom
│   ├── claude/client.py     # CLI subprocess wrapper with retry
│   ├── db/
│   │   ├── database.py      # SQLite init, WAL, singleton
│   │   └── models.py        # Expense, Subscription dataclasses
│   ├── services/
│   │   ├── expense_service.py
│   │   ├── currency_service.py
│   │   ├── subscription_service.py
│   │   └── summary_service.py
│   ├── handlers/
│   │   ├── common.py        # /start, /help, /undo, text parsing
│   │   ├── receipts.py      # Photo + document receipt parsing
│   │   ├── subscriptions.py
│   │   ├── summary.py
│   │   ├── categories.py
│   │   └── currencies.py
│   ├── charts/templates.py  # Plotly visualizations
│   └── prompts/             # System prompts for Claude
├── tests/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Currency Support

31 currencies via Frankfurter.dev API with SQLite cache and stale-rate fallback. All amounts stored in EUR alongside original currency and rate.

## Design Decisions

- **Claude CLI over Python SDK**: Structured output via `--json-schema`, tool use for receipt images, no SDK version coupling.
- **SQLite with WAL**: Single-writer model fits a family bot. WAL mode allows concurrent reads during writes.
- **Singleton DB connection**: One async connection shared across handlers. SQLite doesn't benefit from connection pooling.
- **No inline confirmation yet**: Expenses save immediately. Undo covers mistakes. Confirmation flow is planned.
