from dotenv import dotenv_values


def _get_env_value(key: str) -> str:
    """Helper to get environment variable with consistent error handling."""
    config = dotenv_values(".env")
    value = config.get(key)
    if not value:
        raise ValueError(f"{key} environment variable is not set")
    return value


def get_database_name() -> str:
    """Get the PostgreSQL database name from .env"""
    return _get_env_value("POSTGRES_DB")


def get_database_user() -> str:
    """Get the PostgreSQL user from .env"""
    return _get_env_value("POSTGRES_USER")
