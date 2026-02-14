from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    SHOPIFY_STORE_DOMAIN: str = ""          # empty for now, fill in later
    SHOPIFY_STOREFRONT_ACCESS_TOKEN: str = ""
    SHOPIFY_ADMIN_ACCESS_TOKEN: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    SQLITE_DB_PATH: str = str(BASE_DIR / "data" / "store.db")
    MAX_CONVERSATION_TURNS: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() #type: ignore

"""Key concepts to learn:
- **Pydantic BaseSettings**: auto-loads from environment variables and `.env` files
- **`SettingsConfigDict`**: configure where to find the `.env` file
- **Type validation**: Pydantic ensures each value matches its type annotation """