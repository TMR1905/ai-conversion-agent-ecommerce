from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.models.database import init_db
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: connect DB, load models, etc.
    await init_db(settings.SQLITE_DB_PATH)
    yield
    # shutdown: cleanup resources

app = FastAPI(
    title="AI Conversion Agent for E-Commerce",
    description="An AI-powered chat-based sales assistant that connects to a Shopify store.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}