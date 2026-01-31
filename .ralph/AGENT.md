# Kazo — Agent Configuration

## Prerequisites
- UV (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code` (for CLI backend)
- Optional: `ANTHROPIC_API_KEY` in `.env` (enables faster SDK backend)

## Install Dependencies

```bash
uv sync
```

## Run Tests

```bash
uv run pytest -v
```

## Run Bot

```bash
uv run python -m kazo
```

## Docker

```bash
docker compose up --build
```

## Environment Variables
Copy `.env.example` → `.env`:
- `TELEGRAM_BOT_TOKEN` (required)
- `ALLOWED_CHAT_IDS` — comma-separated chat IDs (optional, empty = allow all)
- `ANTHROPIC_API_KEY` — optional, enables SDK backend for faster responses (~1-2s vs ~10s)
- `DB_PATH` — SQLite file path (default: `kazo.db`)
- `CLAUDE_MODEL` — model name (default: `sonnet`)
- `CLAUDE_TIMEOUT` — seconds (default: `60`)
- `FRANKFURTER_URL` — exchange rate API
- `EXCHANGE_RATE_CACHE_HOURS` — cache TTL (default: `24`)

## Project Layout
- Source: `kazo/`
- Tests: `tests/`
- Config: `pyproject.toml`
- Docker: `Dockerfile`, `docker-compose.yml`
