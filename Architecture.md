# AI Conversion Agent for E-Commerce — Architecture

## Overview
An AI-powered chat-based sales assistant that connects to a Shopify store. The agent uses Claude (Anthropic API) with tool use to search products, answer questions, handle objections, manage carts, and guide customers toward purchase.

**Stack:** FastAPI + Anthropic SDK + Shopify GraphQL APIs + SQLite

---

## Project Structure

```
AI-agent-ecommerce/
├── .env                     # Secrets (API keys, store domain)
├── .env.example             # Template for .env (committed)
├── .gitignore
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory + lifespan (DB init, CORS)
│   ├── config.py            # Pydantic Settings: loads .env, validates config
│   ├── dependencies.py      # FastAPI DI: get_db, get_shopify_client, get_agent
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py        # Top-level router including sub-routers
│   │   ├── chat.py          # POST /api/chat, POST /api/chat/stream
│   │   ├── sessions.py      # CRUD for conversation sessions
│   │   ├── products.py      # GET /api/products (passthrough to Shopify)
│   │   └── health.py        # GET /api/health
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── database.py      # SQLite tables, connection setup (aiosqlite)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent.py         # Core AI agent: Claude + tools + conversation loop
│   │   ├── conversation.py  # Conversation history CRUD, trimming/summarization
│   │   ├── shopify.py       # Shopify API client (Storefront + Admin GraphQL)
│   │   └── tools.py         # Claude tool definitions + execution dispatcher
│   │
│   └── prompts/
│       ├── __init__.py
│       ├── system.py        # System prompt constants
│       └── templates.py     # Dynamic prompt builders (inject cart state, etc.)
│
├── tests/
│   ├── conftest.py
│   ├── test_chat.py
│   ├── test_sessions.py
│   ├── test_shopify.py
│   └── test_agent.py
│
└── data/
    └── store.db             # SQLite file (created at runtime, gitignored)
```

### Layer Responsibilities

- **`api/`** — HTTP layer. Receives requests, validates input, returns responses. No business logic.
- **`services/`** — Business logic. The agent orchestration, Shopify API calls, conversation management.
- **`models/`** — Data shapes. Pydantic schemas for API contracts, database schema and queries.
- **`prompts/`** — AI prompt engineering. Isolated from application logic for easy iteration.

---

## API Endpoints

| Method   | Path                          | Description                          | Request Body       | Response              |
|----------|-------------------------------|--------------------------------------|--------------------|-----------------------|
| `GET`    | `/api/health`                 | Service health check                 | —                  | `{"status": "ok"}`    |
| `POST`   | `/api/sessions`               | Create new chat session              | `{}` or metadata   | `{session_id}`        |
| `GET`    | `/api/sessions/{session_id}`  | Get session + message history        | —                  | Session + messages    |
| `DELETE` | `/api/sessions/{session_id}`  | End/archive a session                | —                  | 204                   |
| `GET`    | `/api/sessions`               | List active sessions                 | query: limit, offset | `[SessionInfo]`     |
| `POST`   | `/api/chat`                   | Send message, get agent reply        | `ChatRequest`      | `ChatResponse`        |
| `POST`   | `/api/chat/stream`            | Send message, get SSE stream         | `ChatRequest`      | SSE stream            |
| `GET`    | `/api/products`               | Search products                      | query: q, limit    | `[ProductSummary]`    |
| `GET`    | `/api/products/{product_id}`  | Get product details                  | —                  | `ProductDetail`       |

### Key Request/Response Models

```python
class ChatRequest(BaseModel):
    session_id: str
    message: str
    metadata: dict | None = None  # optional: page URL, referrer, etc.

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    products_mentioned: list[ProductSummary] | None = None
    cart_url: str | None = None  # checkout URL if cart was created/updated

class ProductSummary(BaseModel):
    id: str
    title: str
    price: str
    image_url: str | None = None
    url: str | None = None
```

### SSE Stream Format (`/api/chat/stream`)

```
event: token
data: {"text": "I'd recommend"}

event: tool_call
data: {"tool": "search_products", "input": {"query": "leather jacket"}}

event: tool_result
data: {"tool": "search_products", "summary": "Found 3 products"}

event: done
data: {"reply": "full reply text...", "products_mentioned": [...]}
```

---

## Database Schema (SQLite)

```sql
-- Conversation sessions
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,                          -- UUID v4
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT,                                      -- JSON: referrer, user-agent, cart_id, etc.
    status      TEXT NOT NULL DEFAULT 'active'             -- 'active' | 'ended'
);

-- Messages within a session
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,                             -- 'user' | 'assistant' | 'tool_result'
    content     TEXT NOT NULL,                             -- message text or JSON for tool blocks
    tool_calls  TEXT,                                      -- JSON: [{name, id, input}] if tool use
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    token_count INTEGER                                    -- for context window management
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

-- Analytics events
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,                             -- 'tool_call' | 'product_viewed' |
                                                          -- 'cart_created' | 'item_added' | 'error'
    event_data  TEXT,                                      -- JSON payload
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, created_at);
```

---

## AI Agent Architecture

### The Agentic Loop (`services/agent.py`)

```
User message arrives via POST /api/chat
    │
    ▼
Load conversation history from DB
    │
    ▼
Build messages array:
  [system_prompt + dynamic context (cart_id), ...history, user_message]
    │
    ▼
Call anthropic.messages.create(model, messages, tools, max_tokens)
    │
    ├── stop_reason == "end_turn"
    │     → Save reply to DB, return ChatResponse
    │
    └── stop_reason == "tool_use"
          → Execute tool(s) via dispatcher
          → Append tool_use + tool_result to messages
          → Call Claude again
          → Loop (max 10 iterations)
```

### Claude Tools (6 tools)

| Tool                  | Purpose                                      | Shopify API    |
|-----------------------|----------------------------------------------|----------------|
| `search_products`     | Search catalog by keyword/type/attributes    | Storefront     |
| `get_product_details` | Full product info with all variants          | Storefront     |
| `check_inventory`     | Stock/availability for a specific variant    | Admin          |
| `create_cart`         | Create cart with items, get checkout URL     | Storefront     |
| `add_to_cart`         | Add items to existing cart                   | Storefront     |
| `get_cart`            | Retrieve current cart contents               | Storefront     |

#### Tool Definition Example

```python
{
    "name": "search_products",
    "description": "Search the product catalog by keyword, product type, or attribute. "
                   "Returns matching products with titles, prices, images, and availability.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query: product name, type, keywords, or attributes"
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (1-10)",
                "default": 5
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "price_asc", "price_desc", "newest", "best_selling"],
                "default": "relevance"
            }
        },
        "required": ["query"]
    }
}
```

#### Tool Dispatcher (`services/tools.py`)

```python
async def execute_tool(tool_name, tool_input, shopify_client, session_context):
    match tool_name:
        case "search_products":
            return await shopify_client.search_products(**tool_input)
        case "get_product_details":
            return await shopify_client.get_product(tool_input["product_id"])
        case "check_inventory":
            return await shopify_client.check_inventory(tool_input["variant_id"])
        case "create_cart":
            cart = await shopify_client.create_cart(tool_input["items"])
            session_context["cart_id"] = cart["id"]
            return cart
        case "add_to_cart":
            return await shopify_client.add_to_cart(tool_input["cart_id"], tool_input["items"])
        case "get_cart":
            return await shopify_client.get_cart(tool_input["cart_id"])
```

### System Prompt Behavior

- Friendly, knowledgeable, not pushy — let the customer lead
- Present 2-3 product recommendations with prices
- Proactively suggest alternatives for out-of-stock items
- Offer cart/checkout links naturally in conversation
- Never invent product information — only state facts from tools
- Handle objections honestly — mention cheaper alternatives if they exist

### Conversation Context Management

1. **Short conversations** (<30 messages): send full history to Claude
2. **Long conversations** (>30 messages): summarize oldest messages into a condensed context block, keep most recent 15 messages intact
3. **Session context injection**: current `cart_id` injected into system prompt so Claude always knows cart state

---

## Shopify Integration (`services/shopify.py`)

### Architecture

- Direct GraphQL via `httpx.AsyncClient` — no Shopify SDK (lighter, async-native, full control)
- **Storefront API** (public token): product search, product details, cart CRUD
- **Admin API** (private token): inventory levels, metafields

### Client Structure

```python
class ShopifyClient:
    def __init__(self, store_domain, storefront_token, admin_token):
        self.storefront_url = f"https://{store_domain}/api/2025-01/graphql.json"
        self.admin_url = f"https://{store_domain}/admin/api/2025-01/graphql.json"
        self._client = httpx.AsyncClient(timeout=15.0)
```

### Key GraphQL Operations

**Product Search (Storefront API):**
```graphql
query SearchProducts($query: String!, $first: Int!) {
  products(query: $query, first: $first, sortKey: RELEVANCE) {
    edges {
      node {
        id, title, description, handle, productType, vendor
        priceRange {
          minVariantPrice { amount, currencyCode }
          maxVariantPrice { amount, currencyCode }
        }
        images(first: 1) { edges { node { url, altText } } }
        variants(first: 10) {
          edges {
            node {
              id, title, availableForSale
              price { amount, currencyCode }
              selectedOptions { name, value }
            }
          }
        }
      }
    }
  }
}
```

**Cart Create (Storefront API):**
```graphql
mutation CartCreate($input: CartInput!) {
  cartCreate(input: $input) {
    cart {
      id, checkoutUrl
      lines(first: 10) {
        edges { node { id, quantity, merchandise { ... on ProductVariant { id, title, price { amount, currencyCode }, product { title } } } } }
      }
      cost { totalAmount { amount, currencyCode } }
    }
    userErrors { field, message }
  }
}
```

### Error Handling

- Catch `httpx` transport errors → raise `ShopifyAPIError`
- Check GraphQL `userErrors` / `errors` in every response
- Log request/response at DEBUG level
- Return parsed, typed data (not raw GraphQL) to callers

---

## Configuration (`config.py`)

```python
class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    SHOPIFY_STORE_DOMAIN: str
    SHOPIFY_STOREFRONT_ACCESS_TOKEN: str
    SHOPIFY_ADMIN_ACCESS_TOKEN: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    SQLITE_DB_PATH: str = "data/store.db"
    MAX_CONVERSATION_TURNS: int = 50
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env")
```

### Environment Variables (`.env`)

```
ANTHROPIC_API_KEY=sk-ant-...
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_STOREFRONT_ACCESS_TOKEN=shpat_...
SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_...
CLAUDE_MODEL=claude-sonnet-4-20250514
SQLITE_DB_PATH=data/store.db
```

---

## Dependencies

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
anthropic>=0.79.0
httpx>=0.27.0
aiosqlite>=0.20.0
pydantic>=2.10.0
pydantic-settings>=2.7.0
python-dotenv>=1.0.0
```

**Rationale:**
- `httpx` over `requests` — native async, required for non-blocking Shopify calls in FastAPI
- `aiosqlite` over raw `sqlite3` — async wrapper so DB ops don't block the event loop
- No Shopify SDK — direct GraphQL is lighter, more predictable, gives full control
- No ORM — for 3 simple tables, raw SQL via `aiosqlite` is more direct

---

## Data Flow Examples

### Flow 1: Product Search Chat

```
Client: POST /api/chat { session_id: "abc", message: "warm winter jackets under $200" }
  → chat.py validates session, saves user message
  → agent.py loads history, calls Claude with tools
  → Claude returns tool_use: search_products(query="winter jacket")
  → tools.py dispatches to shopify.py → Storefront API GraphQL
  → Shopify returns products → tool result sent back to Claude
  → Claude composes response with 2-3 product recommendations
  → agent.py saves assistant message, returns ChatResponse
  → Client receives: reply + products_mentioned[]
```

### Flow 2: Add to Cart

```
Client: POST /api/chat { message: "Add the Alpine Parka in medium to my cart" }
  → Claude calls get_product_details to find Medium variant ID
  → Claude calls create_cart with variant_id + quantity
  → Shopify creates cart, returns cart_id + checkoutUrl
  → Agent saves cart_id to session metadata
  → Claude responds with confirmation + checkout link
  → Client receives: reply + cart_url
```

---

## Implementation Order

1. **Config + Database** — `config.py`, `database.py`
2. **Health + Sessions** — `health.py`, `sessions.py`
3. **Shopify client** — `shopify.py` (product search + details)
4. **Tool definitions** — `tools.py` (JSON schemas + dispatcher)
5. **Agent core** — `agent.py` (Claude tool-use loop)
6. **Chat endpoint** — `chat.py` (wire agent to HTTP)
7. **Streaming** — SSE streaming endpoint
8. **Cart operations** — cart CRUD in Shopify client
9. **Analytics events** — event logging
10. **Conversation management** — history trimming/summarization

---

## Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AI interaction | Manual tool-use loop | Full control over message persistence and session context injection |
| Shopify integration | Direct GraphQL via httpx | Lighter than SDK, async-native, full query control |
| Database | SQLite via aiosqlite | Zero setup, async-compatible, easy PostgreSQL swap later |
| Data access | Raw SQL | 3 simple tables don't justify ORM overhead |
| API split | Storefront + Admin | Storefront for customer ops (products, cart), Admin for inventory/metafields |
