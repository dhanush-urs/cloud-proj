from app.core.config import get_settings


def get_secret_key() -> str:
    settings = get_settings()
    return settings.SECRET_KEY