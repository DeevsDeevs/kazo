# Ralph Fix Plan — Kazo

## Phase 1: Testing Foundation

Nothing ships without tests. Ralph's first job is building the safety net.

- [ ] **Test infrastructure**: Set up pytest + pytest-asyncio. Create `tests/conftest.py` with: in-memory aiosqlite fixture (init schema, yield, close), mock Claude CLI fixture (patch `asyncio.create_subprocess_exec` to return canned JSON), mock httpx fixture for currency API responses. Add pytest + pytest-asyncio to dev dependencies.
- [ ] **Service unit tests**: `tests/test_expense_service.py`, `tests/test_subscription_service.py`, `tests/test_currency_service.py`, `tests/test_summary_service.py`. Cover: save/retrieve/query for each, edge cases (empty results, missing fields, duplicate entries), currency conversion with mocked API and cached rates.
- [ ] **Claude client tests**: `tests/test_claude_client.py`. Mock subprocess responses: valid JSON, malformed JSON, timeout, non-zero exit code, missing `structured_output` field, empty result. Verify each case is handled correctly.
- [ ] **Handler tests**: `tests/test_handlers.py`. Use aiogram test utilities or mock Message/Bot objects. Test: valid expense text → correct response, invalid text → error message, receipt photo flow, subscription commands with valid/invalid args, summary with empty DB.
- [ ] **E2E integration test**: `tests/test_e2e.py`. Full flow with mocked Claude: send text → parse → convert currency → save → query summary → generate chart → verify PNG exists. Also receipt flow. This is the regression safety net.

## Phase 2: Fix Architectural Weaknesses

Address the problems called out in PROMPT.md before adding features.

- [ ] **Intent classification**: Before sending every text to Claude for expense parsing, add a lightweight intent check. Claude classifies the message as `expense`, `query`, or `other`. For `other`, respond with a helpful message instead of wasting a full parse call. Add a new `--json-schema` for intent: `{"intent": "expense"|"query"|"other"}`.
- [ ] **Claude client hardening**: Add retry logic (1 retry on timeout). Log full Claude response at DEBUG level. Validate `--tools ""` actually works (test it). Better error messages that include what Claude returned. Structured logging of latency per call.
- [ ] **Error boundaries**: Add a decorator or middleware that wraps all handlers with try/except, logs traceback, sends "Something went wrong, try again" to user. Currently errors in handlers can cause silent failures.
- [ ] **Receipt improvements**: Accept document messages (PDF, forwarded images) not just photos. Validate parsed total: if items exist and their sum differs from total by >10%, flag it in the response. Fix temp file cleanup to cover the download phase too.
- [ ] **DB transaction safety**: Wrap multi-step writes in explicit transactions. Document that the singleton connection is intentional for SQLite's single-writer model.

## Phase 3: Core UX

Daily-use features that make Kazo actually pleasant.

- [ ] **Inline confirmation**: After parsing an expense, show inline keyboard [Confirm] [Edit] [Cancel]. Only save to DB on Confirm. Auto-confirm after 5 min (use aiogram callback query + scheduled task). This prevents wrong expenses from polluting the data.
- [ ] **Undo**: `/undo` deletes the most recent expense in this chat (must be < 1 hour old). Show what was deleted. Simple and essential.
- [ ] **Edit**: `/edit` shows last expense with current values. User replies with corrections. `/edit 42` for specific expense. Claude parses the correction against original data.
- [ ] **Conversational edits via replies**: When user replies to a bot expense message, detect via `reply_to_message`, look up the expense via message_id→expense_id mapping table, pass original + correction to Claude, update DB. See `specs/conversational-mode.md`.
- [ ] **Natural language queries**: "how much did I spend on groceries?" or "what was my biggest expense last week?" → detect query intent → fetch relevant DB data → pass to Claude with data context → Claude generates natural language answer. Optionally attach a chart.
- [ ] **Multi-message expense**: If Claude returns low-confidence parse (missing amount or ambiguous), bot asks clarifying question. Track pending state per (chat_id, user_id) with 5-min TTL. Next message completes it.

## Phase 4: Useful Features

Build on the solid foundation.

- [ ] **Budget tracking**: `/setbudget 2000` sets monthly EUR budget. `/setbudget groceries 500` per-category. `/summary` shows budget vs actual with progress bar. New `budgets` table: `(chat_id, category TEXT NULL, amount_eur, period DEFAULT 'monthly')`.
- [ ] **Export CSV**: `/export` current month. `/export 2025-01` specific month. Generate CSV in memory, send as Telegram document. Columns: date, amount, currency, EUR amount, category, store, description.
- [ ] **Better charts**: Custom date ranges (`/summary week`, `/summary Q1`, `/summary 2025-01 2025-03`). Cumulative spending line overlay on daily chart. Budget line on monthly chart when budget is set.
- [ ] **Stats**: `/stats` — all-time total, monthly average, top 5 categories, top 5 stores, biggest single expense, current month vs previous month comparison.
- [ ] **Expense search**: `/search coffee` finds expenses matching description/store/items. `/search coffee 2025-01` with date filter.
- [ ] **Subscription billing dates**: Extend subscriptions table with `billing_day`. `/addsub Netflix 15.99 EUR monthly 15` (bills on 15th). Show upcoming billing in `/subs`.
- [ ] **Backup**: `/backup` sends the SQLite DB file as a Telegram document. Simple, no-nonsense data export.
- [ ] **Recurring detection**: After saving an expense, check if same store + similar amount (±20%) appeared 2+ times in last 3 months. If so, suggest: "You seem to pay Store X ~€Y monthly. Add as subscription? /addsub Store X Y EUR monthly".

## Completed
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
- Phases are sequential gates: finish Phase 1 before starting Phase 2
- Test coverage is mandatory for every new feature
