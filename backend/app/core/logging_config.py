import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Создаём директорию для логов, если её нет
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _get_log_level() -> int:
    """Получить уровень логирования из переменной окружения."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Преобразуем строку в уровень логирования
    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    return level_mapping.get(log_level_str, logging.INFO)


def setup_logging() -> None:
    """Настройка логирования для приложения."""
    # Формат логов
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Уровень логирования из переменной окружения или INFO по умолчанию
    log_level = _get_log_level()
    
    # Настройка root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),  # Консоль
            logging.FileHandler(
                LOG_DIR / "app.log",
                encoding="utf-8",
            ),  # Файл
        ],
    )
    
    # Настройка уровней для сторонних библиотек
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # Меньше SQL логов


def get_logger(name: str) -> logging.Logger:
    """Получить logger с указанным именем."""
    return logging.getLogger(name)
