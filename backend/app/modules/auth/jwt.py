"""Создание и верификация JWT access token для входа."""
import uuid
from datetime import datetime, timezone, timedelta

import jwt

from app.core.config import Settings


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    settings: Settings,
) -> str:
    """Создать JWT access token для пользователя."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str, settings: Settings) -> dict:
    """
    Верифицировать JWT и вернуть payload.
    Raises jwt.InvalidTokenError при невалидном токене.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
