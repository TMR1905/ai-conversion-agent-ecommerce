from app.config import settings


def get_db_path() -> str:
    """Provide the database path to endpoint functions."""
    return settings.SQLITE_DB_PATH
