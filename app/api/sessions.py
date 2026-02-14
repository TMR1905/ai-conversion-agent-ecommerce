from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependecies import get_db_path
from app.models.database import (
    create_session,
    get_session,
    list_sessions,
    end_session,
    get_messages,
)
from app.models.schemas import CreateSessionResponse, SessionInfo

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_new_session(db_path: str = Depends(get_db_path)):
    session_id = await create_session(db_path)
    return CreateSessionResponse(session_id=session_id)


@router.get("", response_model=list[SessionInfo])
async def list_all_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db_path: str = Depends(get_db_path),
):
    sessions = await list_sessions(db_path, limit=limit, offset=offset)
    return [
        SessionInfo(
            session_id=s["id"],
            created_at=s["created_at"],
            message_count=0,
            last_active=s["updated_at"],
        )
        for s in sessions
    ]


@router.get("/{session_id}")
async def get_session_detail(
    session_id: str,
    db_path: str = Depends(get_db_path),
):
    session = await get_session(db_path, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await get_messages(db_path, session_id)
    return {
        "session_id": session["id"],
        "created_at": session["created_at"],
        "status": session["status"],
        "messages": messages,
    }


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db_path: str = Depends(get_db_path),
):
    session = await get_session(db_path, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await end_session(db_path, session_id)
