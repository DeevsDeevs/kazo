# Spec: Conversational Mode

## Problem
Currently every text message is blindly sent to Claude for expense parsing. Users can't correct mistakes, ask questions, or interact naturally. The bot feels like a form, not a conversation.

## Solution: Three-tier intent classification

Before doing anything with a text message, classify intent:

```json
{"intent": "expense" | "query" | "other", "confidence": 0.0-1.0}
```

- **expense**: "spent 50 on groceries", "uber 12.50 USD", "lunch at subway" → parse as expense
- **query**: "how much did I spend this month?", "what's my biggest expense?", "show groceries" → answer from DB
- **other**: "hello", "thanks", "ok" → respond politely, don't parse

Low-confidence expense parse (< 0.7): ask follow-up instead of saving garbage.

## Reply-based Edits

### Data model
```sql
CREATE TABLE message_expense_map (
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    expense_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, chat_id)
);
```

### Flow
1. When bot confirms an expense, store `(bot_message_id, chat_id, expense_id)` in mapping table
2. When user replies to a bot message, check if that message_id is in the mapping
3. If yes: load the original expense, pass original data + user's correction text to Claude
4. Claude returns updated fields only (same JSON schema, but only changed fields non-null)
5. Update DB record, send updated confirmation (edit original message if possible)

### Claude prompt for edits
```
Original expense: {original_expense_json}
User correction: "{user_message}"
Return the updated expense. Only change fields the user explicitly mentioned. Keep everything else the same.
```

### Examples
```
User: "lunch at subway 12.50"
Bot: "Expense: €12.50, dining, Subway" [message_id=100, expense_id=42]

User (reply to 100): "that was USD"
→ Load expense 42, send to Claude with correction
→ Claude returns: currency=USD, amount_eur recalculated
Bot: "Updated: $12.50 (€11.43), dining, Subway"
```

## Multi-message Expense

### When to trigger
Claude returns a parse with `confidence < 0.7` or missing required fields (amount, currency).

### State management
In-memory dict, NOT database (ephemeral by design):

```python
@dataclass
class PendingExpense:
    partial: dict          # What Claude could parse so far
    missing: list[str]     # Fields still needed
    created_at: datetime   # For TTL
    prompt_message_id: int # Bot's follow-up question

# Key: (chat_id, user_id) → PendingExpense
# TTL: 5 minutes, checked on access
```

### Flow
1. User: "subway lunch" (no amount)
2. Claude returns: `{store: "Subway", category: "dining", amount: null, confidence: 0.4}`
3. Bot: "Got it — Subway, dining. What was the amount?"
4. User: "12.50" → merge with pending data → save complete expense
5. If user sends something unrelated or 5 min passes → discard pending state

## Natural Language Queries

### When to trigger
Intent classifier returns `query`.

### Flow
1. Detect query intent and extract parameters (time range, category, metric)
2. Run appropriate DB query to get data
3. Pass data + user's question to Claude: "Given this spending data: {data_json}, answer: {user_question}"
4. Claude generates natural language response
5. If query involves trends/comparisons, generate chart and attach

### Example queries
- "how much did I spend on groceries this month?" → SUM where category=groceries, current month
- "what was my biggest expense?" → MAX amount_eur
- "compare last 2 months" → monthly_totals → chart + text summary
