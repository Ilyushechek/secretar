"""
config.py
=========
Модуль для загрузки конфигурации из файла .env.
Использует библиотеку python-dotenv для безопасного хранения секретов.
"""

import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env в окружение
load_dotenv()

# Получаем обязательные параметры из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Получаем параметры почты (опционально)
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))  # По умолчанию порт 587
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Получаем налоговые ставки из окружения (с дефолтными значениями)
TAX_NPD_INDIVIDUAL = float(os.getenv("TAX_NPD_INDIVIDUAL", 4.0))
TAX_NPD_ENTITY = float(os.getenv("TAX_NPD_ENTITY", 6.0))
TAX_NDS = float(os.getenv("TAX_NDS", 0.0))

# Проверяем обязательные параметры
if not BOT_TOKEN or not DATABASE_URL:
    raise ValueError(
        "Ошибка: Не указаны BOT_TOKEN или DATABASE_URL в файле .env\n"
        "Создайте файл .env в корне проекта со следующим содержимым:\n"
        "BOT_TOKEN=ваш_токен\n"
        "DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"
    )

# Экспортируем все параметры для использования в других модулях
__all__ = [
    "BOT_TOKEN",
    "DATABASE_URL",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_USER",
    "EMAIL_PASSWORD",
    "TAX_NPD_INDIVIDUAL",
    "TAX_NPD_ENTITY",
    "TAX_NDS"
]