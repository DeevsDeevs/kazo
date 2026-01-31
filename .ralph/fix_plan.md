# Ralph Fix Plan — Kazo

## Phase 1: Testing Foundation ✓

- [x] **Test infrastructure**: pytest + pytest-asyncio with in-memory aiosqlite fixtures
- [x] **Service unit tests**: expense, subscription, currency, summary services
- [x] **Claude client tests**: subprocess mocking, retry logic, error handling
- [x] **Handler tests**: receipt handlers with photo/document support, MIME validation
- [x] **Category + DB tests**: defaults, custom CRUD, schema constraints

## Phase 2: Fix Architectural Weaknesses ✓

- [x] **Intent classification**: Messages without numbers silently skipped (no wasted API calls)
- [x] **Claude client hardening**: Retry logic (1 retry on timeout/error), DEBUG logging of raw responses
- [x] **Receipt improvements**: Document support (PDF, PNG, JPG, WEBP, HEIC, HEIF), total validation (>10% drift warning), unified temp file cleanup
- [x] **DB transaction safety**: Reviewed — single-statement writes already atomic in SQLite, no changes needed

## Phase 3: Core UX (Partial) ✓

- [x] **Undo**: `/undo` deletes last expense per chat with confirmation message
- [x] **Chart temp files**: Proper cleanup in finally blocks
- [x] **Inline confirmation**: After parsing expense, show [Confirm] [Cancel] inline keyboard. Only save on Confirm. Pending expires after 5 min.
- [ ] **Edit**: `/edit` shows last expense. User replies with corrections. `/edit 42` for specific expense. Claude parses correction against original.
- [ ] **Conversational edits via replies**: Detect reply_to_message, look up expense via message_id mapping, pass original + correction to Claude, update DB.
- [ ] **Natural language queries**: "how much on groceries?" → detect query intent → fetch DB data → Claude generates answer. Optionally attach chart.
- [ ] **Multi-message expense**: Low-confidence parse → bot asks clarifying question. Pending state per (chat_id, user_id) with 5-min TTL.

## Phase 4: Useful Features (Partial)

- [x] **Subscription rate refresh**: `/subs` refreshes EUR amounts via current exchange rates before displaying
- [ ] **Error boundaries**: Decorator/middleware wrapping all handlers with try/except. Log traceback, send "Something went wrong" to user.
- [ ] **Budget tracking**: `/setbudget 2000` monthly EUR budget. `/setbudget groceries 500` per-category. New `budgets` table. `/summary` shows budget vs actual with progress bar.
- [ ] **Export CSV**: `/export` current month. `/export 2025-01` specific month. CSV as Telegram document.
- [ ] **Better charts**: Custom date ranges (`/summary week`, `/summary Q1`). Cumulative spending overlay. Budget line when set.
- [ ] **Stats**: `/stats` — all-time total, monthly avg, top 5 categories/stores, biggest expense, month-over-month comparison.
- [ ] **Expense search**: `/search coffee` matches description/store/items. `/search coffee 2025-01` with date filter.
- [ ] **Subscription billing dates**: `billing_day` column. `/addsub Netflix 15.99 EUR monthly 15`. Show upcoming billing in `/subs`.
- [ ] **Backup**: `/backup` sends SQLite DB file as Telegram document.
- [ ] **Recurring detection**: After saving, check if same store + similar amount (±20%) appeared 2+ times in 3 months. Suggest adding as subscription.

## Phase 5: Hardening & Deploy

- [ ] **Error boundaries**: Wrap all handlers with try/except middleware. Log tracebacks, send generic error to user. No silent failures.
- [ ] **Rate limiting**: Per-chat Claude call limits (e.g., 30/hour) to prevent abuse. Track in memory or DB.
- [ ] **Health check endpoint**: Simple HTTP endpoint for Docker/monitoring. Reports DB connectivity, Claude CLI availability.
- [ ] **Structured logging**: Replace print/logging.info with structured JSON logs. Include chat_id, user_id, handler name, latency.
- [ ] **CI pipeline**: GitHub Actions — run tests on push, lint with ruff, type check with pyright.
- [ ] **Production DB**: Migrate from file SQLite to volume-mounted path. Add backup cron job.
- [ ] **Graceful shutdown**: Handle SIGTERM properly — finish current handler, close DB, stop polling.

## Completed (Pre-Ralph)

- [x] Project scaffolding (pyproject.toml, UV, project structure)
- [x] Claude CLI wrapper (ask_claude, ask_claude_structured)
- [x] Database schema + singleton connection with WAL
- [x] Currency service with validation, caching, stale fallback
- [x] Expense parsing from free text with structured output
- [x] Receipt photo parsing via Claude Read tool
- [x] Subscription CRUD (/subs, /addsub, /removesub)
- [x] Summary charts with Plotly (category, monthly, daily + trend lines)
- [x] Per-chat custom categories (/categories, /addcategory, /removecategory)
- [x] Exchange rate lookup (/rate)
- [x] Auth middleware for allowed chat IDs
- [x] Configurable settings via pydantic-settings
- [x] Docker + docker-compose setup

## Notes
- All work in `kazo/` subfolder
- Conventional commits: `feat:`, `fix:`, `test:`, `refactor:`
- Run `cd kazo && uv sync` before testing
- Claude Code CLI as subprocess, NOT Python SDK
- Test coverage is mandatory for every new feature
