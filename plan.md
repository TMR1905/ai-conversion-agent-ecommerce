# Build Plan — AI E-Commerce Conversion Agent

A step-by-step guide to building this project yourself. Each phase builds on the last.
Verify each step works before moving to the next.

---

## Phase 0: Project Setup
**Goal:** Get the project skeleton running with dependencies installed.

### What to do
- [ ] Create a `.gitignore` (include `venv/`, `data/`, `.env`, `__pycache__/`)
- [ ] Create `.env.example` with all required env var names (no real values)
- [ ] Fill in your `.env` with your real Anthropic API key (you'll add Shopify keys later)
- [ ] Update `requirements.txt` with all dependencies:
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
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create the folder structure:
  ```
  app/
  app/api/
  app/models/
  app/services/
  app/prompts/
  tests/
  data/
  ```
- [ ] Add empty `__init__.py` files in `app/`, `app/api/`, `app/models/`, `app/services/`, `app/prompts/`, `tests/`

### Key concepts to learn
- **Virtual environments (`venv`)**: isolate project dependencies from your system Python
- **`.env` files**: store secrets outside your code so they never get committed to git
- **`__init__.py`**: tells Python a folder is a package that can be imported

### How to verify
- `pip list` shows all your dependencies installed
- Your folder structure matches the Architecture.md layout

---

## Phase 1: Configuration
**Goal:** Load environment variables into typed, validated Python objects.

### What to build
- [ ] `app/config.py` — A `Settings` class using `pydantic_settings.BaseSettings`

### How it works
Pydantic Settings reads your `.env` file automatically and validates that all required values are present. If you forget to set `ANTHROPIC_API_KEY`, the app crashes immediately on startup with a clear error — much better than discovering it mid-request.

### Key fields
```python
ANTHROPIC_API_KEY: str
SHOPIFY_STORE_DOMAIN: str = ""          # empty for now, fill in later
SHOPIFY_STOREFRONT_ACCESS_TOKEN: str = ""
SHOPIFY_ADMIN_ACCESS_TOKEN: str = ""
CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
SQLITE_DB_PATH: str = "data/store.db"
MAX_CONVERSATION_TURNS: int = 50
```

### Key concepts to learn
- **Pydantic BaseSettings**: auto-loads from environment variables and `.env` files
- **`SettingsConfigDict`**: configure where to find the `.env` file
- **Type validation**: Pydantic ensures each value matches its type annotation

### How to verify
Create a quick test script:
```python
from app.config import Settings
settings = Settings()
print(settings.ANTHROPIC_API_KEY[:10] + "...")  # should print first 10 chars
print(settings.SQLITE_DB_PATH)                   # should print "data/store.db"
```

---

## Phase 2: Database Layer
**Goal:** Create SQLite tables and write helper functions for reading/writing data.

### What to build
- [ ] `app/models/database.py` — Database initialization and CRUD functions

### What to implement
1. **`init_db(db_path)`** — creates the 3 tables (sessions, messages, events) if they don't exist
2. **`create_session(db, metadata)`** — inserts a new session row, returns session_id (use `uuid4()`)
3. **`get_session(db, session_id)`** — fetches a session by ID
4. **`save_message(db, session_id, role, content, tool_calls)`** — inserts a message
5. **`get_messages(db, session_id)`** — returns all messages for a session, ordered by `created_at`
6. **`log_event(db, session_id, event_type, event_data)`** — inserts an analytics event

### Key concepts to learn
- **`aiosqlite`**: an async wrapper around Python's built-in `sqlite3`. FastAPI is async, so all I/O (including database) should be non-blocking
- **`async with aiosqlite.connect(path) as db`**: opens a connection
- **`await db.execute(sql, params)`**: runs a query with parameterized values (NEVER use f-strings for SQL — that's SQL injection)
- **`await db.fetchone()` / `await db.fetchall()`**: get results
- **`await db.commit()`**: save changes to disk
- **UUID v4**: universally unique IDs — use `str(uuid.uuid4())` for session IDs

### SQL reference
Copy the CREATE TABLE statements from Architecture.md — they're ready to use.

### How to verify
Write a test script:
```python
import asyncio
from app.models.database import init_db, create_session, save_message, get_messages

async def test():
    db_path = "data/test.db"
    await init_db(db_path)

    session_id = await create_session(db_path, metadata=None)
    print(f"Created session: {session_id}")

    await save_message(db_path, session_id, "user", "Hello!", None)
    await save_message(db_path, session_id, "assistant", "Hi! How can I help?", None)

    messages = await get_messages(db_path, session_id)
    for msg in messages:
        print(f"  {msg['role']}: {msg['content']}")

asyncio.run(test())
```
Delete `data/test.db` when done.

---

## Phase 3: FastAPI App + Health & Session Endpoints
**Goal:** Get the FastAPI server running with your first working endpoints.

### What to build
- [ ] `app/main.py` — FastAPI app with lifespan (DB init on startup)
- [ ] `app/api/health.py` — `GET /api/health`
- [ ] `app/api/sessions.py` — Session CRUD endpoints
- [ ] `app/api/router.py` — Combines all sub-routers
- [ ] `app/models/schemas.py` — Pydantic request/response models
- [ ] `app/dependencies.py` — FastAPI dependency injection

### Step by step

**3a. `app/main.py`**
- Create a FastAPI app with `lifespan` async context manager
- In the lifespan `startup`: call `init_db()` to create tables
- Add CORS middleware (allow all origins for development)
- Include the router from `app/api/router.py`

**3b. `app/models/schemas.py`**
- Define `CreateSessionResponse(BaseModel)` with `session_id: str`
- Define `SessionInfo(BaseModel)` with `session_id`, `created_at`, `message_count`, `last_active`
- You'll add `ChatRequest` and `ChatResponse` later

**3c. `app/dependencies.py`**
- Write a `get_db()` dependency that yields an aiosqlite connection
- This is where FastAPI's dependency injection shines — endpoints declare what they need, FastAPI provides it

**3d. `app/api/health.py`**
- Single endpoint: `GET /api/health` → returns `{"status": "ok"}`

**3e. `app/api/sessions.py`**
- `POST /api/sessions` — create session, return session_id
- `GET /api/sessions/{session_id}` — get session info + messages
- `DELETE /api/sessions/{session_id}` — mark session as ended
- `GET /api/sessions` — list all active sessions

**3f. `app/api/router.py`**
- Create an `APIRouter` that includes health and sessions routers

### Key concepts to learn
- **FastAPI lifespan**: replaces the old `@app.on_event("startup")` pattern. It's an async context manager where you do setup before `yield` and cleanup after
- **Dependency injection**: `Depends(get_db)` in endpoint signatures — FastAPI calls `get_db()` for you, passes the result, and cleans up after the request
- **APIRouter**: lets you organize endpoints into separate files and combine them
- **CORS middleware**: allows browsers to call your API from different domains

### How to verify
```bash
uvicorn app.main:app --reload
```
Then test in your browser or with curl:
- `GET http://localhost:8000/api/health` → `{"status": "ok"}`
- `POST http://localhost:8000/api/sessions` → `{"session_id": "some-uuid"}`
- `GET http://localhost:8000/api/sessions/{that-uuid}` → session data
- Visit `http://localhost:8000/docs` → Swagger UI shows all your endpoints

---

## Phase 4: Shopify Client
**Goal:** Connect to a real Shopify store and fetch products.

### Prerequisites
You need a Shopify store with API access. Options:
- Create a free Shopify Partner development store at https://partners.shopify.com
- Use an existing store
- Create a custom app in Shopify Admin → Settings → Apps → Develop apps
- Get your **Storefront API** access token and **Admin API** access token
- Add both tokens + store domain to your `.env`

### What to build
- [ ] `app/services/shopify.py` — `ShopifyClient` class

### What to implement (start with these 2, add more later)
1. **`search_products(query, limit, sort_key)`** — Storefront API GraphQL query
2. **`get_product(product_id)`** — Storefront API, single product with variants

### How it works
Shopify's APIs use GraphQL. You send a POST request with a JSON body containing a `query` string and `variables` object. The response contains the data you requested.

### Starter hint
```python
class ShopifyClient:
    def __init__(self, store_domain, storefront_token, admin_token):
        self.storefront_url = f"https://{store_domain}/api/2025-01/graphql.json"
        self._client = httpx.AsyncClient(timeout=15.0)
        self.storefront_headers = {
            "X-Shopify-Storefront-Access-Token": storefront_token,
            "Content-Type": "application/json",
        }

    async def _storefront_query(self, query, variables=None):
        """Send a GraphQL query to the Storefront API."""
        response = await self._client.post(
            self.storefront_url,
            headers=self.storefront_headers,
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise Exception(f"Shopify API error: {data['errors']}")
        return data["data"]
```

### Key concepts to learn
- **GraphQL**: unlike REST (one URL per resource), GraphQL uses a single endpoint where you specify exactly what data you want in the query. This means fewer requests and no over-fetching
- **`httpx.AsyncClient`**: async HTTP client — like `requests` but non-blocking. Reuse a single client instance for connection pooling
- **Shopify GIDs**: Shopify IDs look like `gid://shopify/Product/123456` — they're globally unique identifiers

### How to verify
Write a test script:
```python
import asyncio
from app.config import Settings
from app.services.shopify import ShopifyClient

async def test():
    settings = Settings()
    client = ShopifyClient(
        settings.SHOPIFY_STORE_DOMAIN,
        settings.SHOPIFY_STOREFRONT_ACCESS_TOKEN,
        settings.SHOPIFY_ADMIN_ACCESS_TOKEN,
    )
    products = await client.search_products("shirt", limit=3)
    for p in products:
        print(f"{p['title']} - ${p['price']}")

asyncio.run(test())
```
You should see real products from your Shopify store.

---

## Phase 5: Tool Definitions
**Goal:** Define the tools Claude can use and build the dispatcher.

### What to build
- [ ] `app/services/tools.py` — Tool schemas + `execute_tool()` function

### What to implement
1. **`TOOL_DEFINITIONS`** — a list of dictionaries, each following Anthropic's tool schema format (see Architecture.md for examples)
2. **`execute_tool(tool_name, tool_input, shopify_client, session_context)`** — a dispatcher that maps tool names to actual function calls

### Start with 2 tools
- `search_products` — maps to `shopify_client.search_products()`
- `get_product_details` — maps to `shopify_client.get_product()`

You'll add cart tools later in Phase 9.

### Key concepts to learn
- **Claude tool use**: you give Claude a list of tools (name + description + JSON schema for inputs). Claude decides when to call them and generates the input. Your code executes the tool and sends the result back
- **JSON Schema**: a standard way to describe the shape of JSON data. Claude uses this to know what parameters each tool accepts
- **`match/case`** (Python 3.10+): a clean way to dispatch based on tool name — like a switch statement

### How to verify
Test the tool definitions are valid by importing them:
```python
from app.services.tools import TOOL_DEFINITIONS
import json
print(json.dumps(TOOL_DEFINITIONS, indent=2))
```
Each tool should have `name`, `description`, and `input_schema` with `type`, `properties`, and `required`.

---

## Phase 6: System Prompt
**Goal:** Define how the AI agent behaves.

### What to build
- [ ] `app/prompts/system.py` — The system prompt constant
- [ ] `app/prompts/templates.py` — Function to build dynamic context

### What to implement
1. **`SALES_AGENT_SYSTEM_PROMPT`** — a multi-paragraph string defining the agent's personality, capabilities, and rules (see Architecture.md for the full prompt)
2. **`build_system_prompt(cart_id=None)`** — takes the base prompt and appends dynamic context like "The customer's current cart ID is: ..."

### Key concepts to learn
- **System prompts**: the instruction that shapes Claude's behavior for the entire conversation. Unlike user messages, the system prompt is persistent context
- **Prompt engineering**: the description, rules, and examples you put in the system prompt directly affect output quality. Be specific about what the agent should/shouldn't do
- **Dynamic context injection**: appending runtime information (cart state, session metadata) to the system prompt so Claude has full awareness

### Tips for writing a good sales prompt
- Be explicit about tone ("friendly but not pushy")
- Set boundaries ("never invent product information")
- Give concrete behavioral rules ("present 2-3 options, always include prices")
- Define what to do in edge cases ("if out of stock, suggest alternatives")

### How to verify
Just read it and make sure it sounds like the sales assistant you want. You'll test it end-to-end in Phase 7.

---

## Phase 7: The AI Agent (Core)
**Goal:** Build the heart of the system — the Claude tool-use loop.

This is the most important phase. Take your time here.

### What to build
- [ ] `app/services/agent.py` — `SalesAgent` class
- [ ] `app/services/conversation.py` — Conversation history loading/saving

### What to implement

**`app/services/conversation.py`:**
1. **`load_history(db, session_id)`** — loads messages from DB, formats them for Claude's API
2. **`save_turn(db, session_id, user_msg, assistant_msg, tool_calls)`** — saves both sides of a conversation turn

**`app/services/agent.py`:**
1. **`SalesAgent.__init__(anthropic_client, shopify_client, settings)`** — store dependencies
2. **`SalesAgent.process_message(db, session_id, user_message)`** — the main method:

### The agentic loop (step by step)
```
1. Load conversation history from DB
2. Build system prompt (with cart context if exists)
3. Build messages list: [...history, {"role": "user", "content": user_message}]
4. Call anthropic_client.messages.create(
       model=model, system=system_prompt,
       messages=messages, tools=TOOL_DEFINITIONS, max_tokens=1024
   )
5. Check response.stop_reason:
   - "end_turn" → extract text from response.content, save to DB, return
   - "tool_use" → continue to step 6
6. Extract tool_use blocks from response.content
7. For each tool_use block:
   - Call execute_tool(block.name, block.input, shopify_client, session_ctx)
   - Collect the result
8. Append to messages:
   - The assistant's response (contains both text + tool_use blocks)
   - A user message with tool_results:
     [{"type": "tool_result", "tool_use_id": block.id, "content": result_json}]
9. Call Claude again with the updated messages
10. Go back to step 5 (max 10 iterations for safety)
```

### The tool-use loop visualized
```
You send:  messages + tools
Claude:    "I need to search for products" → tool_use block
You:       Execute search_products() → get results
You send:  messages + tool_use + tool_result
Claude:    "Here are some great options..." → end_turn (final text)
```

Claude might chain multiple tools (search → get details → check inventory) before responding. Your loop handles this automatically.

### Key concepts to learn
- **Anthropic Messages API**: `client.messages.create()` — the core API call
- **`stop_reason`**: tells you why Claude stopped. `"end_turn"` = done talking, `"tool_use"` = wants to call a tool
- **`response.content`**: a list of content blocks — can be `TextBlock` (text) or `ToolUseBlock` (tool call)
- **Tool result format**: you send tool results back as a user message with `content` being a list of `{"type": "tool_result", "tool_use_id": "...", "content": "..."}`

### How to verify
Write a test script:
```python
import asyncio
import anthropic
from app.services.agent import SalesAgent
from app.services.shopify import ShopifyClient
from app.config import Settings
from app.models.database import init_db, create_session

async def test():
    settings = Settings()
    await init_db(settings.SQLITE_DB_PATH)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    shopify = ShopifyClient(
        settings.SHOPIFY_STORE_DOMAIN,
        settings.SHOPIFY_STOREFRONT_ACCESS_TOKEN,
        settings.SHOPIFY_ADMIN_ACCESS_TOKEN,
    )
    agent = SalesAgent(client, shopify, settings)

    session_id = await create_session(settings.SQLITE_DB_PATH, None)
    response = await agent.process_message(
        settings.SQLITE_DB_PATH, session_id,
        "What running shoes do you have under $100?"
    )
    print(response.reply)
    print(f"Products mentioned: {response.products_mentioned}")

asyncio.run(test())
```
You should see a natural response mentioning real products from your store.

---

## Phase 8: Chat Endpoint
**Goal:** Wire the agent into HTTP so clients can chat via API.

### What to build
- [ ] `app/api/chat.py` — `POST /api/chat` endpoint
- [ ] Update `app/models/schemas.py` — Add `ChatRequest`, `ChatResponse`, `ProductSummary`
- [ ] Update `app/dependencies.py` — Add `get_agent()` dependency
- [ ] Update `app/api/router.py` — Include the chat router

### Schemas to add
```python
class ChatRequest(BaseModel):
    session_id: str
    message: str

class ProductSummary(BaseModel):
    id: str
    title: str
    price: str
    image_url: str | None = None
    url: str | None = None

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    products_mentioned: list[ProductSummary] | None = None
    cart_url: str | None = None
```

### `POST /api/chat` endpoint logic
1. Validate the session exists (return 404 if not)
2. Call `agent.process_message(db, request.session_id, request.message)`
3. Return the `ChatResponse`

### Key concepts to learn
- **FastAPI dependency chain**: `get_agent()` depends on `get_shopify_client()` which depends on `Settings` — FastAPI resolves the entire chain for you
- **Request validation**: FastAPI + Pydantic automatically validates the request body against `ChatRequest` and returns 422 errors if invalid
- **Error handling**: use `HTTPException(status_code=404)` when session not found

### How to verify
```bash
uvicorn app.main:app --reload
```
Then use the Swagger UI at `http://localhost:8000/docs`:
1. Create a session via `POST /api/sessions`
2. Send a chat via `POST /api/chat` with the session_id and a message like "What products do you have?"
3. You should get a real AI response with product recommendations

This is a big milestone — you have a working AI sales agent!

---

## Phase 9: Cart Operations
**Goal:** Let the AI agent create carts and add items for customers.

### What to build
- [ ] Add to `app/services/shopify.py`:
  - `create_cart(items)` — Storefront API `cartCreate` mutation
  - `add_to_cart(cart_id, items)` — `cartLinesAdd` mutation
  - `get_cart(cart_id)` — cart query
  - `check_inventory(variant_id)` — Admin API inventory query
- [ ] Add to `app/services/tools.py`:
  - `create_cart`, `add_to_cart`, `get_cart`, `check_inventory` tool definitions
  - Update `execute_tool()` dispatcher with new cases
- [ ] Update session metadata storage to persist `cart_id`

### Key concepts to learn
- **GraphQL mutations**: unlike queries (read-only), mutations change data (create cart, add items). Same HTTP request format, different operation type
- **Shopify Cart API**: Storefront API manages carts. `cartCreate` returns a `checkoutUrl` the customer can use to complete their purchase — this is the conversion moment
- **Session state**: the `cart_id` needs to persist across messages. Store it in the session's `metadata` JSON column and inject it into the system prompt

### How to verify
Chat with the agent:
1. "Show me your best t-shirts"
2. "Add the first one to my cart"
3. The response should include a checkout URL
4. Open the checkout URL in your browser — it should show a real Shopify checkout

---

## Phase 10: Streaming (SSE)
**Goal:** Stream the agent's response token-by-token for a real-time chat feel.

### What to build
- [ ] `POST /api/chat/stream` in `app/api/chat.py`
- [ ] Update `app/services/agent.py` — Add `process_message_stream()` method

### How it works
Instead of `client.messages.create()`, use `client.messages.stream()` which returns an async iterator of events. Wrap this in FastAPI's `StreamingResponse` with `media_type="text/event-stream"`.

### SSE event format
```
event: token
data: {"text": "partial text here"}

event: tool_call
data: {"tool": "search_products", "input": {"query": "jacket"}}

event: tool_result
data: {"tool": "search_products", "summary": "Found 3 products"}

event: done
data: {"reply": "full response", "products_mentioned": [...]}
```

### Key concepts to learn
- **Server-Sent Events (SSE)**: a simple protocol for server → client streaming over HTTP. The client opens a long-lived connection, and the server sends events as they happen
- **`StreamingResponse`**: FastAPI's way to send chunked/streaming responses
- **Anthropic streaming API**: `client.messages.stream()` yields delta events with partial text as Claude generates it

### How to verify
Use curl to test streaming:
```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-id", "message": "Tell me about your products"}'
```
You should see events appearing one by one, not all at once.

---

## Phase 11: Analytics & Conversation Management
**Goal:** Track conversion events and handle long conversations gracefully.

### What to build
- [ ] Add event logging throughout `agent.py` — log `product_viewed`, `cart_created`, `item_added` events to the `events` table whenever those actions happen
- [ ] Add conversation trimming to `app/services/conversation.py`:
  - When message count exceeds 30, summarize the oldest messages into a single condensed context block
  - Keep the most recent 15 messages intact so Claude has immediate context

### Key concepts to learn
- **Token management**: Claude has a context window limit. Long conversations will eventually exceed it. Summarizing old messages keeps the conversation going indefinitely
- **Conversion funnel analytics**: tracking which products were viewed, carted, and purchased helps measure the agent's effectiveness

### How to verify
- Check the `events` table after a conversation: `SELECT * FROM events WHERE session_id = ?`
- Have a very long conversation (30+ messages) and verify the agent still works correctly and remembers recent context

---

## Bonus Ideas (after completing all phases)

- [ ] **Authentication**: add API key auth or JWT tokens to protect endpoints
- [ ] **Rate limiting**: prevent abuse of the chat endpoint
- [ ] **Webhook handling**: receive Shopify order webhooks to track actual conversions
- [ ] **Multiple store support**: make the agent work with different Shopify stores
- [ ] **Frontend chat widget**: build a simple HTML/JS chat widget to embed on a website
- [ ] **Deployment**: deploy to Railway, Render, or AWS

---

## Quick Reference

### Run the server
```bash
uvicorn app.main:app --reload
```

### API docs (auto-generated)
```
http://localhost:8000/docs
```

### Key files by importance
| Priority | File | What it does |
|----------|------|--------------|
| 1 | `app/services/agent.py` | The AI brain — Claude tool-use loop |
| 2 | `app/services/shopify.py` | Shopify GraphQL integration |
| 3 | `app/services/tools.py` | What the AI can do (tool definitions) |
| 4 | `app/prompts/system.py` | How the AI behaves (personality/rules) |
| 5 | `app/api/chat.py` | HTTP entry point for chat |
| 6 | `app/models/database.py` | Data persistence layer |

### Useful documentation
- Anthropic tool use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages
- Anthropic streaming: https://docs.anthropic.com/en/api/streaming
- Shopify Storefront API: https://shopify.dev/docs/api/storefront
- Shopify Cart API: https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api/cart
- FastAPI docs: https://fastapi.tiangolo.com
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- aiosqlite: https://github.com/omnilib/aiosqlite
