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