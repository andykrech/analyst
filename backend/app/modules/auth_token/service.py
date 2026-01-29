import secrets
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.modules.auth_token.model import AuthToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_token() -> str:
    """Генерировать безопасный одноразовый токен."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Хешировать токен для хранения в БД."""
    return pwd_context.hash(token)


def verify_token(token: str, token_hash: str) -> bool:
    """
    Проверить токен против хеша.
    
    Args:
        token: Токен в открытом виде
        token_hash: Хешированный токен из БД
        
    Returns:
        True если токен совпадает, False иначе.
    """
    try:
        return pwd_context.verify(token, token_hash)
    except Exception:
        return False


async def create_verify_email_token(
    session: AsyncSession,
    user_id: uuid.UUID,
    expires_at: datetime | None = None,
) -> tuple[AuthToken, str]:
    """
    Создать токен для подтверждения email.
    
    Returns:
        tuple: (AuthToken объект, raw_token строка)
    """
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    raw_token = generate_token()
    token_hash = hash_token(raw_token)
    
    auth_token = AuthToken(
        user_id=user_id,
        token_hash=token_hash,
        purpose="verify_email",
        expires_at=expires_at,
        used_at=None,
    )
    
    session.add(auth_token)
    await session.flush()
    await session.refresh(auth_token)
    
    return auth_token, raw_token


async def find_and_consume_verify_email_token(
    session: AsyncSession,
    raw_token: str,
) -> AuthToken | None:
    """
    Найти токен подтверждения email по сырой строке, пометить как использованный.
    SELECT ... FOR UPDATE защищает от гонки при одновременных запросах с одним токеном.
    Возвращает AuthToken (с user_id) или None, если токен не найден/истёк/уже использован.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(AuthToken)
        .where(
            AuthToken.purpose == "verify_email",
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > now,
        )
        .with_for_update()
    )
    for auth_token in result.scalars().all():
        if verify_token(raw_token, auth_token.token_hash):
            auth_token.used_at = now
            await session.flush()
            return auth_token
    return None


async def find_used_verify_email_token(
    session: AsyncSession,
    raw_token: str,
) -> AuthToken | None:
    """
    Найти уже использованный токен verify_email по сырой строке (для идемпотентного ответа).
    Если пользователь повторно переходит по ссылке — возвращаем 200 "Email already verified".
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(AuthToken).where(
            AuthToken.purpose == "verify_email",
            AuthToken.used_at.isnot(None),
            AuthToken.expires_at > now,
        )
    )
    for auth_token in result.scalars().all():
        if verify_token(raw_token, auth_token.token_hash):
            return auth_token
    return None
