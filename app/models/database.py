import uuid
import json
from pathlib import Path
import aiosqlite


async def init_db(db_path: str):
    """Create tables if they don't exist. Called once on app startup."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                metadata    TEXT,
                status      TEXT NOT NULL DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                tool_calls  TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                token_count INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at);

            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                event_type  TEXT NOT NULL,
                event_data  TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_events_session
                ON events(session_id);

            CREATE INDEX IF NOT EXISTS idx_events_type
                ON events(event_type, created_at);
        """)
        await db.commit()


# --- Session CRUD ---

async def create_session(db_path: str, metadata: dict | None = None) -> str:
    """Create a new conversation session. Returns the session_id."""
    session_id = str(uuid.uuid4())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO sessions (id, metadata) VALUES (?, ?)",
            (session_id, json.dumps(metadata) if metadata else None),
        )
        await db.commit()
    return session_id


async def get_session(db_path: str, session_id: str) -> dict | None:
    """Fetch a session by ID. Returns None if not found."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def list_sessions(db_path: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """List active sessions, most recent first."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE status = 'active' ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def end_session(db_path: str, session_id: str):
    """Mark a session as ended."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE sessions SET status = 'ended', updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        await db.commit()


# --- Message CRUD ---

async def save_message(
    db_path: str,
    session_id: str,
    role: str,
    content: str,
    tool_calls: list[dict] | None = None,
) -> int | None:
    """Save a message to the conversation. Returns the message id."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls) VALUES (?, ?, ?, ?)",
            (session_id, role, content, json.dumps(tool_calls) if tool_calls else None),
        )
        # Update the session's updated_at timestamp
        await db.execute(
            "UPDATE sessions SET updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        await db.commit()
        return cursor.lastrowid


async def get_messages(db_path: str, session_id: str) -> list[dict]:
    """Load all messages for a session, oldest first."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Event Logging ---

async def log_event(
    db_path: str,
    session_id: str,
    event_type: str,
    event_data: dict | None = None,
):
    """Log an analytics event (product_viewed, cart_created, etc.)."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO events (session_id, event_type, event_data) VALUES (?, ?, ?)",
            (session_id, event_type, json.dumps(event_data) if event_data else None),
        )
        await db.commit()
