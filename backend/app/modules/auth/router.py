import logging
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.email import AuthEmailService
from app.modules.auth.jwt import create_access_token, decode_access_token
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    VerifyResponse,
)
from app.modules.user.model import User
from app.modules.user.service import (
    get_by_email,
    get_by_id,
    create_user_inactive,
    hash_password,
    confirm_email,
    verify_password,
)
from app.modules.auth_token.service import (
    create_verify_email_token,
    find_and_consume_verify_email_token,
    find_used_verify_email_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

logger = logging.getLogger(__name__)


def get_auth_email_service(request: Request) -> AuthEmailService:
    """Возвращает AuthEmailService из app.state (инициализируется при старте)."""
    return request.app.state.auth_email_service


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Извлечь текущего пользователя из Authorization: Bearer <token>. 401 при отсутствии или невалидном токене."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = auth[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_access_token(token, get_settings())
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user = await get_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    auth_email_service: AuthEmailService = Depends(get_auth_email_service),
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
        
        # Отправляем письмо с ссылкой подтверждения
        settings = get_settings()
        verify_link = f"{settings.FRONTEND_BASE_URL}/verify?token={raw_token}"
        await auth_email_service.send_verification_email(
            to_email=request.email,
            verify_link=verify_link,
        )
        
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


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Вход по email и паролю.
    Возвращает access_token (JWT) и email.
    Требуется подтверждённый email.
    """
    user = await get_by_email(db, request.email)
    if not user:
        logger.warning(f"Login attempt for unknown email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Login failed: invalid password for {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    settings = get_settings()
    token = create_access_token(user.id, user.email, settings)
    logger.info(f"User logged in: {user.email} (user_id: {user.id})")
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        email=user.email,
    )


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """
    Текущий пользователь по JWT.
    Восстановление состояния после reload, задел под роли.
    """
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        roles=[],  # позже: из модели/сервиса ролей
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    """
    Подтверждение email по одноразовой ссылке из письма.
    GET /api/v1/auth/verify?token=...
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required",
        )
    raw = token.strip()
    auth_token = await find_and_consume_verify_email_token(db, raw)
    if not auth_token or not auth_token.user_id:
        # Повторный переход по ссылке: токен уже использован — вернуть 200 "already verified"
        used_token = await find_used_verify_email_token(db, raw)
        if used_token and used_token.user_id:
            user = await get_by_id(db, used_token.user_id)
            if user and user.email_verified_at is not None:
                await db.commit()
                logger.info(f"Email already verified (reused link) for user_id={user.id}")
                return VerifyResponse(message="Email already verified")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )
    user = await get_by_id(db, auth_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )
    if user.email_verified_at is not None:
        await db.commit()
        logger.info(f"Email already verified for user_id={user.id}")
        return VerifyResponse(message="Email already verified")
    user = await confirm_email(db, auth_token.user_id)
    await db.commit()
    logger.info(f"Email verified for user_id={user.id}")
    return VerifyResponse(message="Email verified successfully")
