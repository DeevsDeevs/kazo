# Kazo Fix Plan

## Phase 1: Test Foundation (BLOCKING — must complete before Phase 2)

- [x] 1.1 Add pytest + pytest-asyncio to dev deps
- [x] 1.2 Create conftest.py with in-memory SQLite fixture
- [x] 1.3 Tests: DB layer (init_db, get_db, schema creation)
- [x] 1.4 Tests: expense_service (save, query with date filters)
- [x] 1.5 Tests: subscription_service (add, list, remove)
- [x] 1.6 Tests: currency_service (validate, cache, convert, stale fallback)
- [x] 1.7 Tests: summary_service (by_category, monthly, daily)
- [x] 1.8 Tests: categories (defaults, custom CRUD)
- [x] 1.9 Tests: claude/client.py (mock subprocess, structured output, errors, timeout)

## Phase 2: Critical Bug Fixes

- [x] 2.1 Claude CLI: add retry logic (1 retry on transient failure)
- [x] 2.2 Claude CLI: log raw responses at DEBUG level
- [x] 2.3 DB: reviewed — all writes are single-statement + commit, no multi-statement transactions needed
- [x] 2.4 Intent classification: skip messages without numbers (no API call wasted)

## Phase 3: Robustness

- [x] 3.1 Receipt handler: fix temp file cleanup scope
- [x] 3.2 Receipt handler: validate parsed total vs item sum (warning log on >10% mismatch)
- [x] 3.3 Add expense undo (/undo command, delete_last_expense service)
- [x] 3.4 Chart temp file cleanup: close fd before write_image

## Phase 4: Enhancements

- [ ] 4.1 Subscription rate refresh on /subs
- [ ] 4.2 Document-type receipt support (PDF)

## Discoveries

_(New issues found during work go here)_
