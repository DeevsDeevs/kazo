# Spec: Testing Strategy

## Why This Is Phase 1

Ralph operates autonomously. Without tests, it has no way to verify its changes don't break things. Every subsequent phase depends on having a solid test suite that Ralph can run after each change.

## Test Structure

```
kazo/tests/
├── conftest.py              # Shared fixtures
├── test_claude_client.py    # Claude CLI subprocess mocking
├── test_currency_service.py # Exchange rate logic
├── test_expense_service.py  # Expense CRUD
├── test_subscription_service.py
├── test_summary_service.py  # Aggregation queries
├── test_handlers.py         # Telegram handler logic
└── test_e2e.py              # Full flow integration
```

## Key Fixtures (conftest.py)

### In-memory DB
```python
@pytest.fixture
async def db():
    """Fresh in-memory SQLite with schema applied."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await conn.commit()
    # Patch get_db to return this connection
    with patch("kazo.db.database.get_db", return_value=conn):
        yield conn
    await conn.close()
```

### Mock Claude CLI
```python
@pytest.fixture
def mock_claude():
    """Patch subprocess to return canned Claude responses."""
    def _make_mock(response: dict):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            json.dumps(response).encode(),
            b"",
        )
        mock_proc.returncode = 0
        return mock_proc
    # Usage: mock_claude({"result": "...", "structured_output": {...}})
    ...
```

### Mock httpx (currency API)
```python
@pytest.fixture
def mock_currency_api():
    """Mock frankfurter.dev responses."""
    with patch("kazo.services.currency_service.httpx.AsyncClient") as mock:
        ...
```

## What to Test

### Claude Client
- Valid structured output → returns parsed dict
- Valid text output → returns string
- Malformed JSON → raises RuntimeError with context
- Subprocess timeout → raises TimeoutError
- Non-zero exit code → raises RuntimeError with stderr
- Missing `structured_output` key → raises RuntimeError
- `structured_output` as string (needs JSON parse) → returns dict

### Currency Service
- EUR → EUR returns rate 1.0, no API call
- Cache miss → fetches from API → caches → returns rate
- Cache hit (fresh) → returns cached rate, no API call
- Cache expired → fetches fresh rate
- API failure + fresh cache → raises
- API failure + stale cache → returns stale rate with warning
- Invalid currency code → raises InvalidCurrencyError
- Unsupported currency → raises InvalidCurrencyError

### Expense Service
- Save expense → returns ID > 0
- Save + retrieve by chat_id → matches
- Date range filtering works correctly
- Empty results → returns empty list

### Handlers
- Text expense "spent 50 on groceries" → message.answer called with confirmation containing amount, category
- Invalid/unparseable text → error message
- Photo message → "Processing receipt..." → confirmation
- /subs with no subs → "No active subscriptions"
- /addsub with valid args → success message
- /addsub with missing args → usage message
- /summary with empty DB → "No expenses this month"

### E2E
- Full text expense flow: mock Claude returning `{amount: 50, currency: "EUR", category: "groceries", ...}` → verify expense in DB with correct EUR conversion
- Full receipt flow: mock Claude returning receipt data → verify expense saved with items_json
- Summary flow: insert test expenses → call summary → verify chart file generated
