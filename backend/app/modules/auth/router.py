import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.modules.auth.schemas import RegisterRequest, RegisterResponse
from app.modules.user.service import (
    get_by_email,
    create_user_inactive,
    hash_password,
)
from app.modules.auth_token.service import create_verify_email_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

logger = logging.getLogger(__name__)

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Регистрация нового пользователя.
    
    Создаёт пользователя с неподтверждённым email и отправляет письмо
    с одноразовой ссылкой для подтверждения.
    """
    # Проверяем, что пользователя с таким email нет
    existing_user = await get_by_email(db, request.email)
    if existing_user:
        logger.warning(f"Registration attempt with existing email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    # Хешируем пароль
    hashed_password = hash_password(request.password)
    
    try:
        # Создаём пользователя
        user = await create_user_inactive(
            session=db,
            email=request.email,
            hashed_password=hashed_password,
        )
        
        # Создаём токен подтверждения email
        auth_token, raw_token = await create_verify_email_token(
            session=db,
            user_id=user.id,
        )
        
        # Отправляем письмо (заглушка)
        verification_url = f"{FRONTEND_BASE_URL}/verify?token={raw_token}"
        logger.info(
            f"Verification email sent to {request.email}. "
            f"Verification URL: {verification_url}"
        )
        # TODO: Реальная отправка email
        
        await db.commit()
        
        logger.info(f"User registered successfully: {request.email} (user_id: {user.id})")
        
        return RegisterResponse(message="Verification email sent")
    
    except IntegrityError:
        await db.rollback()
        logger.error(f"Integrity error during registration for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Registration failed for email {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )
