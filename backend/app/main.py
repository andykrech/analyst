import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.core.logging_config import setup_logging
from app.modules.auth.router import router as auth_router

# Настраиваем логирование при старте приложения
setup_logging()

app = FastAPI(
    title="Analyst API",
    description="Analyst application API",
    version="1.0.0",
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


@app.get("/api", response_class=PlainTextResponse)
def analyst() -> str:
    return "Analyst"
