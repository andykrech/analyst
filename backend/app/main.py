import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.integrations.email import AuthEmailService, get_email_sender
from app.integrations.llm import LLMService
from app.db.session import AsyncSessionLocal
from app.modules.billing.service import BillingService
from app.integrations.search import SearchService
from app.integrations.search.router import router as search_router
from app.integrations.translation import TranslationService
from app.modules.auth.router import router as auth_router
from app.modules.entity.router import router as entity_router
from app.modules.event.router import router as event_router
from app.modules.landscape.router import router as landscape_router
from app.modules.quanta.router import router as quanta_router
from app.modules.site.router import router as site_router
from app.modules.theme.router import router as theme_router
from app.modules.user.router import router as user_router
from app.modules.billing.router import router as billing_router

# Настраиваем логирование при старте приложения
setup_logging()

logger = logging.getLogger(__name__)


async def _run_billing_rollup_on_startup(billing_service: BillingService) -> None:
    """До 3 попыток свернуть детальный биллинг в дневные строки; при неудаче — только лог."""
    for attempt in range(1, 4):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await billing_service.rollup_usage_events_to_daily(session)
            return
        except Exception as e:
            logger.warning(
                "Свёртка биллинга при старте: попытка %s/3 не удалась: %s",
                attempt,
                e,
                exc_info=(attempt == 3),
            )
            if attempt < 3:
                await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при старте: конфиг, email-сервис, LLM-сервис."""
    settings = get_settings()
    email_sender = get_email_sender(settings)
    app.state.auth_email_service = AuthEmailService(email_sender)
    app.state.billing_service = BillingService()
    await _run_billing_rollup_on_startup(app.state.billing_service)
    app.state.llm_service = LLMService(settings, billing_service=app.state.billing_service)
    app.state.search_service = SearchService(settings, billing_service=app.state.billing_service)
    app.state.translation_service = TranslationService(settings, billing_service=app.state.billing_service)

    yield
    # shutdown при необходимости


app = FastAPI(
    title="Analyst API",
    description="Analyst application API",
    version="1.0.0",
    lifespan=lifespan,
)

# Настройка CORS
# Читаем разрешённые origins из переменной окружения
cors_origins_str = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"  # Дефолт для локальной разработки
)

# Разбиваем строку на список origins
allowed_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

# Добавляем CORS middleware ДО подключения роутеров
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Список конкретных origins (не ["*"])
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

app.include_router(auth_router)
app.include_router(site_router)
app.include_router(theme_router)
app.include_router(user_router)
app.include_router(search_router)
app.include_router(quanta_router)
app.include_router(entity_router)
app.include_router(event_router)
app.include_router(landscape_router)
app.include_router(billing_router)


@app.get("/api", response_class=PlainTextResponse)
def analyst() -> str:
    return "Analyst"
