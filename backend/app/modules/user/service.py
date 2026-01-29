import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.user.model import User
from passlib.context import CryptContext

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Получить пользователя по id."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def confirm_email(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Установить email_verified_at для пользователя (идемпотентно: не перезаписывает, если уже установлен). Возвращает пользователя или None."""
    user = await get_by_id(session, user_id)
    if not user:
        return None
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        await session.flush()
    return user


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    """Получить пользователя по email."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user_inactive(
    session: AsyncSession,
    email: str,
    hashed_password: str,
) -> User:
    """Создать неактивного пользователя (email не подтверждён)."""
    user = User(
        email=email,
        hashed_password=hashed_password,
        email_verified_at=None,
        is_active=True,  # Пользователь активен, но email не подтверждён
    )
    session.add(user)
    await session.flush()  # Получаем ID пользователя
    await session.refresh(user)
    return user


def hash_password(password: str) -> str:
    """Хешировать пароль с помощью passlib/bcrypt."""
    # Логирование перед хешированием
    password_bytes = password.encode('utf-8')
    password_length_chars = len(password)
    password_length_bytes = len(password_bytes)
    password_preview = password[:10] + "..." if len(password) > 10 else password
    
    logger.debug(
        f"Hash password: length_chars={password_length_chars}, "
        f"length_bytes={password_length_bytes}, "
        f"preview='{password_preview}'"
    )
    
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    Проверить пароль против хеша.
    
    Args:
        password: Пароль в открытом виде
        hashed: Хешированный пароль из БД
        
    Returns:
        True если пароль совпадает, False иначе.
    """
    return pwd_context.verify(password, hashed)
