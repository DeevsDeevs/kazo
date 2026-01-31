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

## Phase 4: Dual Backend — Claude API + CLI (NEW — Top Priority)

The Claude CLI subprocess has ~9s startup overhead per call. When `ANTHROPIC_API_KEY` is set in `.env`, use the Anthropic Python SDK directly for ~1-2s responses. Fall back to CLI when no API key is configured (uses Claude subscription credits).

- [x] **Add anthropic SDK dependency**: `uv add anthropic`. Add `anthropic_api_key: str | None = None` to `Settings` in config.py. When set, use SDK. When unset, use CLI as before.
- [x] **SDK backend in claude/client.py**: `_ask_sdk()` uses `anthropic.AsyncAnthropic` with `messages.create()`. `_ask_sdk_structured()` uses tool_use with json_schema as tool definition. Image/receipt passed as base64 (no Read tool needed).
- [x] **Backend router**: `_use_sdk()` checks `settings.anthropic_api_key`. `ask_claude` and `ask_claude_structured` route to SDK or CLI transparently.
- [x] **Test both backends**: 8 new SDK tests + 7 existing CLI tests all passing. Router tests verify correct dispatch.
- [x] **Update /help and README**: Document the two backends. If API key is configured, mention faster response times.

## Phase 5: Expense Editing & Item Tracking

Receipt items are already parsed by Claude and stored as JSON in `items_json`, but they're not queryable. This phase normalizes item data and adds editing capabilities. Editing should work via natural conversational text — user just replies with what to change.

- [x] **Expense edit via conversation**: User replies to a bot expense confirmation message with a correction in natural language (e.g., "that was dining not groceries" or "amount was actually 45"). Detect `reply_to_message` on bot messages, look up expense via `bot_message_expenses` table (`bot_message_id → expense_id`). Store mapping on confirm. Pass original expense + user correction to Claude, update DB. No slash command needed — just reply to edit.
- [x] **`/edit` command as fallback**: `/edit` shows last expense with current values. `/edit 42` for specific expense by ID. User replies with corrections. Claude parses correction against original and updates DB.
- [x] **Receipt edit flow**: After receipt confirmation, allow editing parsed items before saving. Show inline keyboard per item: [Keep] [Remove]. User can remove items that weren't theirs or fix wrong prices via reply.
- [x] **Items table**: New `expense_items` table: `(id, expense_id FK, name TEXT, price REAL, currency TEXT, quantity REAL DEFAULT 1)`. Migrate existing `items_json` data into this table. Keep `items_json` on expenses for backward compat but write to both. Index on `(name)` for price lookups.
- [x] **Item price history**: `/price tomatoes` — queries `expense_items` by name (fuzzy match via LIKE), returns price history across receipts with dates and stores. Shows min/avg/max and trend. `/price tomatoes lidl` filters by store.
- [x] **Item search**: `/items` lists recently purchased items. `/items groceries` filters by category. Shows item name, last price, last store, last date.
- [x] **Price comparison**: `/compare tomatoes` shows price across different stores sorted by price. Helps find cheapest store for specific items over time.

## Phase 6: Product Photo Recognition & Smart Parsing

Not just receipts — users can photograph products themselves (grocery bags, fridge contents, items on a table). Claude identifies products from the image and helps log them as expenses.

- [x] **Product photo handler**: Detect when a photo is NOT a receipt (no store name, no total, no line items). Instead of failing, switch to product identification mode. Claude lists recognized products from the image with estimated quantities. Bot responds with the product list and asks: "What was the total?" or "Want to add prices per item?"
- [x] **Conversational price entry**: After product identification, user can reply with total ("was 45 euros") or per-item prices ("tomatoes 3.50, bread 2.20, the rest was about 15"). Claude parses this against the identified product list and fills in prices. Partial pricing is fine — unpriced items split the remainder.
- [x] **Product list confirmation**: Show identified products with inline keyboard [Confirm All] [Edit List]. User can remove misidentified items or add missing ones via reply. Once confirmed + priced, save as expense with full item breakdown.
- [x] **Smart photo routing**: Single photo handler that auto-detects: receipt (has store/total/line items) → receipt flow, product photo (visible products, no receipt format) → product identification flow. Use Claude to classify.

## Phase 7: Prompt Tuning & UX Polish

Every feature should be accessible both via slash commands AND natural conversation. Go over each function and ensure dual access.

- [x] **Prompt audit and tuning**: Review all prompts in `prompts/` directory. Tune for accuracy: expense parsing should handle edge cases (multiple currencies, date references like "yesterday", ambiguous amounts). Receipt parsing should handle blurry/partial receipts gracefully. Product photo parsing should be specific about quantities and product names.
- [x] **Conversational access audit**: Go through every feature and ensure it works both ways:
  - Expense: text message with amount ✓ (already works)
  - Undo: `/undo` ✓ AND "undo that" or "delete last one" → should also trigger undo
  - Edit: reply to message ✓ AND "change last expense to dining" → should detect edit intent
  - Summary: `/summary` ✓ AND "how much did I spend this month?" → natural language query
  - Categories: `/categories` ✓ AND "show my categories" or "add a category called pets"
  - Subscriptions: `/subs` ✓ AND "show my subscriptions" or "add netflix 15.99 monthly"
  - Rate: `/rate USD` ✓ AND "what's the dollar rate?"
  - Search: `/search coffee` AND "find my coffee expenses"
  - Price: `/price tomatoes` AND "how much were tomatoes last time?"
- [x] **Intent classifier upgrade**: Current classifier just checks for numbers. Upgrade to detect: expense, query, edit, undo, subscription management, category management, help request, and general chat. Use Claude with a lightweight intent schema. Cache recent intents to avoid duplicate calls.
- [x] **Translate receipt/product items to English**: Update receipt and product photo prompts to instruct Claude to translate all item names to English (e.g., "pommes de terre" → "potatoes", "Vollmilch" → "whole milk") while preserving brand names as-is (e.g., "Danone", "Lidl"). This ensures consistent item names for price history, search, and comparisons regardless of store language.
- [x] **Helpful responses for non-expense messages**: When user says "thanks", "hello", or asks a question, respond naturally instead of silently ignoring. Brief, friendly, not annoying.

## Phase 8: Configurable Base Currency ✓

EUR is hardcoded across ~40 places in the codebase (display strings, comparisons, chart labels, handler messages). Make it configurable so users can set their home currency.

- [x] **Add `base_currency` to Settings**: New field in `config.py` with default `"EUR"`. Also add `/setcurrency USD` command (stores per-chat in DB, falls back to config default). Add `CURRENCY_SYMBOLS` map: `{"EUR": "€", "USD": "$", "GBP": "£", ...}` for display.
- [x] **Refactor currency_service.py**: Replace all hardcoded `"EUR"` with `get_base_currency(chat_id)`. `convert_to_base()` replaces `convert_to_eur()`. DB column `amount_eur` stays as-is for backward compat but stores base currency amount. Add migration note.
- [x] **Refactor display strings**: All handlers use `format_amount(amount, chat_id)` helper that returns e.g. `"€45.00"` or `"$45.00"` based on chat's base currency. Replace every `f"€{amount:.2f}"` pattern. Affects: common.py, receipts.py, subscriptions.py, summary.py, budget.py, pending.py, export.py, items.py.
- [x] **Refactor charts**: `templates.py` — replace hardcoded `"EUR"` axis labels with base currency code. Pass currency to chart functions.
- [x] **Settings command**: `/settings` shows current config (base currency, model, etc). `/setcurrency USD` changes base currency for this chat. Store in new `chat_settings` table.

## Phase 9: More Features (was Phase 8)

- [x] **Subscription rate refresh**: `/subs` refreshes EUR amounts via current exchange rates before displaying
- [x] **Error boundaries**: Decorator/middleware wrapping all handlers with try/except. Log traceback, send "Something went wrong" to user.
- [x] **Budget tracking**: `/setbudget 2000` monthly EUR budget. `/setbudget groceries 500` per-category. New `budgets` table. `/summary` shows budget vs actual with progress bar.
- [x] **Export CSV**: `/export` current month. `/export 2025-01` specific month. CSV as Telegram document.
- [x] **Better charts**: Custom date ranges (`/summary week`, `/summary Q1`). Cumulative spending overlay on daily chart. Budget line on daily chart when set.
- [x] **Stats**: `/stats` — all-time total, monthly avg, top 5 categories/stores, biggest expense, month-over-month comparison.
- [x] **Expense search**: `/search coffee` matches description/store/items. `/search coffee 2025-01` with date filter.
- [x] **Expense notes**: Add optional `note TEXT` column to `expenses` table. Notes can be added inline ("spent 10 on coffee with note birthday gift"), retrospectively via reply ("add note: birthday gift"), or via `/note 42 birthday gift`. Claude parses note from natural language — keywords like "note", "comment", "memo", "reason". Show notes in expense confirmations, `/search` results, and export CSV. When generating `/summary` or answering natural language queries, pass notes to Claude so it can provide richer context (e.g., "you spent more on dining this month — mostly birthday celebrations").
- [x] **Subscription billing dates**: `billing_day` column. `/addsub Netflix 15.99 EUR monthly 15`. Show upcoming billing in `/subs`.
- [x] **Backup**: `/backup` sends SQLite DB file as Telegram document.
- [x] **Recurring detection**: After saving, check if same store + similar amount (±20%) appeared 2+ times in 3 months. Suggest adding as subscription.
- [x] **Natural language queries**: "how much on groceries?" → detect query intent → fetch DB data → Claude generates answer. Optionally attach chart.
- [ ] **Item parsing from text messages**: When user lists items with prices in a text message (e.g., "carrefour tomatoes 2.50 potatoes 1.80 salad 2.40"), parse each item individually and save to `expense_items` table — same as receipt flow. Update expense parsing prompt to return `items` array with `{name, price}` when per-item prices are provided. Handler saves to `expense_items` via existing `_save_items_from_json`. Without per-item prices (just "tomatoes potatoes salad 6.70"), store item names without prices for searchability.

## Phase 10: Hardening & Deploy

- [x] **Error boundaries**: Wrap all handlers with try/except middleware. Log tracebacks, send generic error to user. No silent failures.
- [x] **Rate limiting**: Per-chat Claude call limits (30/hour default, configurable via `rate_limit_per_hour`). In-memory sliding window in main.py, enforced in `ask_claude`/`ask_claude_structured` via `chat_id` param. RateLimitExceeded caught by error boundary with user-friendly message. 7 tests.
- [x] **Health check endpoint**: asyncio TCP server on configurable port (default 8080). Returns JSON with DB connectivity, Claude CLI availability, SDK status. 503 when DB is down. 2 tests.
- [x] **Structured logging**: JSON formatter in `kazo/logging.py`. `setup_logging()` called in main.py. All handler log calls include `extra={"chat_id": ...}` context. 4 new tests.
- [x] **CI pipeline**: GitHub Actions — run tests on push, lint with ruff, type check with pyright.
- [x] **Production DB**: Volume-mounted at `./data:/app/data` via docker-compose. `DB_PATH` env var configurable. `/backup` command for manual backups.
- [x] **Graceful shutdown**: aiogram handles SIGTERM/SIGINT, stops polling, lets in-flight handlers finish. Finally block closes health server and DB with logging.
- [x] **Update /help command**: `/start` is concise onboarding, `/help` shows comprehensive command reference organized by category (tracking, editing, reports, items, setup).

## Phase 11: Code Quality — Ruff + Review

- [x] **Add ruff**: Configured `[tool.ruff]` in `pyproject.toml` (line-length 120, target Python 3.13, select rules: E, F, I, UP, B, SIM, RUF). Already had ruff as dev dependency.
- [x] **Format entire codebase**: Ran `ruff format .` (36 files reformatted) and `ruff check --fix .` (46 auto-fixed). Fixed 16 remaining: duplicate `cmd_help`, bare raises without `from`, long lines, unused vars, ambiguous unicode, double-split in items.py.
- [x] **Re-review each module**: Python dev review found: dead `get_rate_to_eur`/`convert_to_eur` (removed), double-split in items.py (fixed), duplicated progress bar calc in summary.py (fixed). Noted but deferred: broad except clauses, display logic duplication, magic numbers.
- [x] **Verify tests still pass**: 149 tests passing after all changes.
- [x] **Update README**: Rewrite README.md to focus on functionality and user-facing features (what Kazo does, all commands, how to use conversational features, photo/receipt support, budgets, subscriptions, etc). Less codebase internals, more "here's what you can do with it". Keep setup/install/docker instructions.

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
- Claude Code CLI as subprocess when no API key; Anthropic SDK when ANTHROPIC_API_KEY is set
- Test coverage is mandatory for every new feature
