# Kazo

Family finance bot for Telegram. Text it an expense, photograph a receipt, snap a bag of groceries, ask how much you spent — it handles all of it.

## What it does

**Track expenses** — send "lunch 12.50" or "coffee 4 usd" and it logs it. Supports any of 31 currencies with automatic conversion. Add notes inline: "dinner 45 note birthday celebration".

**Scan receipts** — send a photo or PDF of a receipt. Kazo extracts the store, items, prices, and total. Works with any language — item names get translated to English automatically so price history stays consistent.

**Photograph products** — not a receipt, just a bag of groceries or items on a table. Kazo identifies the products and asks you for prices. You can give a total or per-item breakdown.

**Edit anything** — reply to any expense confirmation to correct it ("that was dining not groceries", "amount was 45"). Or use `/edit` to fix the last one.

**Inline confirmation** — every expense shows Confirm/Cancel buttons before saving. No accidental entries.

**Budgets** — set monthly limits overall or per-category. Summaries show progress bars against your budget.

**Track item prices** — receipt items are stored individually. Check price history, compare across stores, search by name.

**Natural language** — ask "how much did I spend on groceries this month?" and get an answer. Say "undo that" instead of `/undo`. Say "show my subscriptions" instead of `/subs`. Everything works both ways.

## Commands

### Tracking
| Command | What it does |
|---------|-------------|
| *any text with amount* | Log an expense ("coffee 4.50", "uber 23 usd") |
| *photo/PDF* | Parse receipt or identify products |
| `/undo` | Delete last expense |
| `/edit [id]` | Edit last expense (or by ID) |
| `/note ID text` | Add note to an expense |

### Reports
| Command | What it does |
|---------|-------------|
| `/summary [week\|month\|Q1]` | Spending breakdown with chart |
| `/monthly` | 6-month trend chart |
| `/daily` | Last 30 days chart |
| `/stats` | All-time stats, top categories/stores, biggest expense |
| `/export [YYYY-MM]` | Download CSV |
| `/backup` | Download SQLite database file |

### Items & Prices
| Command | What it does |
|---------|-------------|
| `/price tomatoes [store]` | Price history across receipts |
| `/items [category]` | Recently purchased items |
| `/compare tomatoes` | Price comparison across stores |
| `/search coffee [date]` | Find expenses by keyword |

### Subscriptions
| Command | What it does |
|---------|-------------|
| `/subs` | List active subscriptions with current rates |
| `/addsub Name Amount Currency [frequency] [billing_day]` | Add subscription |
| `/removesub Name` | Deactivate subscription |

### Settings
| Command | What it does |
|---------|-------------|
| `/setcurrency USD` | Change base currency for this chat |
| `/setbudget 2000` | Set monthly budget (or `/setbudget groceries 500`) |
| `/categories` | List categories |
| `/addcategory Name` | Add custom category |
| `/removecategory Name` | Remove category |
| `/rate [Currency]` | Exchange rate lookup |
| `/settings` | View current configuration |
| `/help` | Full command reference |

## Setup

### Prerequisites

- Python 3.13+
- [UV](https://docs.astral.sh/uv/)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Anthropic API key (for Claude)

### Install & Configure

```bash
cd kazo
uv sync
cp .env.example .env
```

Fill in `.env`:

```bash
TELEGRAM_BOT_TOKEN=your-token
ANTHROPIC_API_KEY=your-key
ALLOWED_CHAT_IDS=123456789           # comma-separated, optional
BASE_CURRENCY=EUR                     # default
CLAUDE_MODEL=haiku                    # haiku, sonnet, or opus
```

### Run

```bash
uv run python -m kazo
```

### Docker

```bash
docker compose up -d
```

Data persists in `./data/` via volume mount.

## Tests

```bash
uv run pytest
```

149 tests covering all services, handlers, database, Claude client, and item tracking.
