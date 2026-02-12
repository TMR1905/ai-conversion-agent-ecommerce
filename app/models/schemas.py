from pydantic import BaseModel


# --- Session schemas ---

class CreateSessionResponse(BaseModel):
    session_id: str


class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    message_count: int
    last_active: str


# --- Chat schemas (Phase 8) ---

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
