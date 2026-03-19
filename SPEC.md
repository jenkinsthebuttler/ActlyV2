# Actly v2 — Spec

## What it is

**Headless, agent-first AI tool marketplace.** AI agents discover it, register, and pay per tool execution — fully autonomously, no humans needed after setup.

## The loop

```
Agent discovers → GET /.well-known/agent-capabilities.json
Agent registers → POST /auth/register → {api_key, wallet_address, 10 free credits}
Agent works → POST /execute (deducts credits per call)
Agent runs low → sends ETH to wallet_address (any exchange or wallet)
Agent deposits → POST /payments/crypto/deposit {tx_hash} → credits added, agent continues
```

## Core design principle

Zero human in the loop after registration. Every payment path works for an AI agent.

---

## Tech stack

- **Python 3.11** / FastAPI / Uvicorn
- **PostgreSQL** (async via `asyncpg` + SQLAlchemy 2.0)
- **bcrypt** for API key hashing
- **httpx** for fetch tool
- **Playwright** for browser screenshots
- **Docker** for deployment

---

## Data model

```sql
Agent
  id            UUID PRIMARY KEY
  wallet_address  VARCHAR(42) NOT NULL  -- random 20-byte hex, deposit-only
  credits       NUMERIC(10,4) DEFAULT 10.0000  -- starts with 10 free credits
  created_at    TIMESTAMPTZ DEFAULT NOW()

Transaction
  id            UUID PRIMARY KEY
  agent_id      UUID FK → Agent
  amount        NUMERIC(10,4) NOT NULL  -- positive = credit, negative = debit
  type          VARCHAR(20)  -- 'topup_crypto' | 'topup_stripe' | 'execution'
  idempotency_key VARCHAR(255) UNIQUE NOT NULL
  created_at    TIMESTAMPTZ DEFAULT NOW()

ApiKey
  id            UUID PRIMARY KEY
  agent_id      UUID FK → Agent
  key_hash      VARCHAR(255) NOT NULL  -- bcrypt
  key_prefix    VARCHAR(20) UNIQUE NOT NULL  -- indexed for fast lookup
  is_active     BOOLEAN DEFAULT TRUE
  created_at    TIMESTAMPTZ DEFAULT NOW()

ExecutionLog
  id            UUID PRIMARY KEY
  agent_id      UUID FK → Agent
  tool          VARCHAR(64) NOT NULL
  params        JSONB
  output        JSONB
  credits_charged NUMERIC(10,4)
  was_free      BOOLEAN DEFAULT FALSE
  status        VARCHAR(16)  -- 'success' | 'error'
  duration_ms   INTEGER
  created_at    TIMESTAMPTZ DEFAULT NOW()
```

---

## API endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/.well-known/agent-capabilities.json` | Agent discovery manifest |
| GET | `/skills` | List tools (name, description, price) |
| GET | `/skills/{name}` | Single tool schema |
| GET | `/health` | Health check |

### Auth-free register

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create agent → api_key + wallet_address + 10 free credits |

### Authenticated (X-API-Key header)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/balance` | Credits remaining |
| POST | `/execute` | Run a tool |
| POST | `/payments/stripe` | Get Stripe checkout URL |
| POST | `/payments/crypto/deposit` | Verify ETH tx, add credits |
| GET | `/logs` | Execution history |

---

## Payment flow

### Stripe (human-friendly)
1. `POST /payments/stripe` → returns checkout URL
2. Human opens URL, pays
3. Webhook confirms → credits added

### Crypto (agent-friendly, zero human)
1. Agent reads `wallet_address` from register response
2. Sends ETH/USDC to that address (any wallet, any exchange)
3. Agent calls `POST /payments/crypto/deposit` with tx hash
4. Server verifies tx on-chain via Ethereum RPC
5. Credits added (1 USD = 1 credit, ETH valued at $2000)

### Free tier
- Every new agent starts with **10 free credits**
- Each tool has a free daily limit (e.g., 50 fetch_text/day)
- Paid calls deduct from credits balance

---

## Tool registry

Tools are auto-discovered Python classes in `app/tools/`.

Each tool:
- `name` — identifier
- `description` — for agent discovery
- `input_schema` — JSON Schema
- `price_per_call` — Decimal (0 = free)
- `daily_free_limit` — int or None
- `async execute(params) → ToolResult`

### Built-in tools

| Tool | Price | Daily free | Description |
|------|-------|-----------|-------------|
| `fetch_text` | $0 | 100/day | HTTP GET → plain text, up to 5000 chars |
| `browser_screenshot` | $0.01 | 2/day | Playwright screenshot of URL |

---

## MCP endpoint

`POST /mcp` — JSON-RPC 2.0 over HTTP

Methods:
- `initialize` → protocol version, server info
- `tools/list` → all available tools with schemas
- `tools/call` → execute a tool (requires X-API-Key)

---

## Error codes

| Code | Meaning |
|------|---------|
| 401 | Missing or invalid API key |
| 402 | Insufficient credits — response includes wallet_address + deposit instructions |
| 404 | Tool not found |
| 429 | Daily free limit exceeded |
| 500 | Tool execution failed |

---

## Deployment

### Railway
```bash
railway up
```

### Docker
```bash
docker compose up
```

### Coolify
- Connect GitHub repo
- Add PostgreSQL plugin
- Set env vars: `DATABASE_URL`, `SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `BASE_URL`
- Deploy

---

## What's NOT in v2 (stripped)

- No email/multi-key per agent (single key, simple)
- No file storage (keep it minimal)
- No MCP subscribe/notifications (maybe later)
- No OpenClaw adapter package (use MCP or REST directly)
- No admin dashboard (agents don't need it)
- No complex analytics (just `/logs` endpoint)
