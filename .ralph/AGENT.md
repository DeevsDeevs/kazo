# Kazo — Agent Configuration

## Prerequisites
- UV (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 22+ (for Claude Code CLI)
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Environment: `ANTHROPIC_API_KEY` must be set

## Install Dependencies

```bash
cd kazo && uv sync
```

## Run Tests

```bash
cd kazo && uv run python -m pytest tests/ -v
```

## Verify Imports (quick smoke test)

```bash
cd kazo && TELEGRAM_BOT_TOKEN=test uv run python -c "from kazo.main import main; print('OK')"
```

## Run Bot

```bash
cd kazo && uv run python -m kazo
```

## Docker

```bash
cd kazo && docker compose up --build
```

## Environment Variables
Copy `kazo/.env.example` → `kazo/.env`:
- `TELEGRAM_BOT_TOKEN` (required)
- `ALLOWED_CHAT_IDS` — comma-separated chat IDs (optional, empty = allow all)
- `DB_PATH` — SQLite file path (default: `kazo.db`)
- `CLAUDE_MODEL` — model name (default: `sonnet`)
- `CLAUDE_TIMEOUT` — seconds (default: `60`)
- `FRANKFURTER_URL` — exchange rate API (default: `https://api.frankfurter.dev/v1/latest`)
- `EXCHANGE_RATE_CACHE_HOURS` — cache TTL (default: `24`)

## Project Layout
- Source: `kazo/kazo/`
- Tests: `kazo/tests/`
- Config: `kazo/pyproject.toml`
- Docker: `kazo/Dockerfile`, `kazo/docker-compose.yml`
