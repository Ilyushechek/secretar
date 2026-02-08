"""
database.py
===========
Модуль для работы с базой данных PostgreSQL.
Использует асинхронную библиотеку asyncpg для высокой производительности.
"""

import asyncpg
import bcrypt
import random
import string
from datetime import datetime, timedelta, date as date_type
import logging  # ← ДОБАВЛЕНО для логгера
from config import DATABASE_URL
from math import radians, sin, cos, sqrt, atan2  # ← для геокодирования
from geopy.geocoders import Nominatim  # ← для геокодирования
from geopy.exc import GeocoderTimedOut, GeocoderServiceError  # ← для геокодирования
import asyncio  # ← для асинхронного геокодирования

logger = logging.getLogger(__name__)  # ← ДОБАВЛЕНО

# ============================================================================
# ФУНКЦИИ ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ
# ============================================================================

async def get_db_connection():
    """
    Создаёт асинхронное подключение к PostgreSQL.
    
    Returns:
        asyncpg.Connection: Объект подключения к БД
    """
    return await asyncpg.connect(DATABASE_URL)


# ============================================================================
# ФУНКЦИИ РЕГИСТРАЦИИ И АУТЕНТИФИКАЦИИ
# ============================================================================

async def is_user_registered(telegram_id: int) -> bool:
    """
    Проверяет, зарегистрирован ли пользователь в системе.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
    
    Returns:
        bool: True если пользователь зарегистрирован, иначе False
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT 1 FROM users WHERE telegram_id = $1", 
            telegram_id
        )
        return row is not None
    finally:
        await conn.close()


async def create_user(telegram_id: int, password_hash: str) -> str:
    """
    Создаёт нового пользователя в системе и генерирует 6-значный код.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
        password_hash (str): Хэш пароля (bcrypt)
    
    Returns:
        str: Уникальный 6-значный код пользователя
    """
    conn = await get_db_connection()
    try:
        # Генерируем уникальный 6-значный код
        while True:
            user_code = ''.join(random.choices(string.digits, k=6))
            exists = await conn.fetchrow(
                "SELECT 1 FROM users WHERE user_code = $1", 
                user_code
            )
            if not exists:
                break
        
        # Вставляем нового пользователя в таблицу users
        await conn.execute(
            """
            INSERT INTO users (telegram_id, password_hash, user_code) 
            VALUES ($1, $2, $3)
            """,
            telegram_id, password_hash, user_code
        )
        return user_code
    finally:
        await conn.close()


async def get_password_hash(telegram_id: int) -> str:
    """
    Получает хэш пароля пользователя из БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
    
    Returns:
        str: Хэш пароля или None, если пользователь не найден
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE telegram_id = $1", 
            telegram_id
        )
        return row["password_hash"] if row else None
    finally:
        await conn.close()


async def update_password(telegram_id: int, password_hash: str):
    """
    Обновляет пароль пользователя в БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
        password_hash (str): Новый хэш пароля
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE telegram_id = $2", 
            password_hash, telegram_id
        )
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С EMAIL И СБРОСОМ ПАРОЛЯ
# ============================================================================

async def update_user_email(telegram_id: int, email: str):
    """
    Сохраняет email пользователя в БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
        email (str): Email адрес пользователя
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE users SET email = $1 WHERE telegram_id = $2", 
            email, telegram_id
        )
    finally:
        await conn.close()


async def get_user_email(telegram_id: int):
    """
    Получает email пользователя из БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
    
    Returns:
        str: Email или None, если не задан
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT email FROM users WHERE telegram_id = $1", 
            telegram_id
        )
        return row["email"] if row else None
    finally:
        await conn.close()


async def generate_reset_code(telegram_id: int):
    """
    Генерирует 6-значный код для сброса пароля и сохраняет его в БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
    
    Returns:
        str: Сгенерированный код (6 цифр)
    """
    code = ''.join(random.choices(string.digits, k=6))
    expires = datetime.utcnow() + timedelta(minutes=10)
    
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            UPDATE users 
            SET reset_code = $1, reset_code_expires = $2 
            WHERE telegram_id = $3
            """,
            code, expires, telegram_id
        )
        return code
    finally:
        await conn.close()


async def verify_reset_code(telegram_id: int, code: str) -> bool:
    """
    Проверяет валидность кода сброса пароля.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
        code (str): Введённый пользователем код
    
    Returns:
        bool: True если код валиден, иначе False
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT reset_code, reset_code_expires 
            FROM users 
            WHERE telegram_id = $1
            """,
            telegram_id
        )
        
        if not row or not row["reset_code"] or not row["reset_code_expires"]:
            return False
        
        if row["reset_code"] != code:
            return False
        
        if row["reset_code_expires"] < datetime.utcnow():
            return False
        
        return True
    finally:
        await conn.close()


async def clear_reset_code(telegram_id: int):
    """
    Очищает код сброса пароля после успешного использования.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            UPDATE users 
            SET reset_code = NULL, reset_code_expires = NULL 
            WHERE telegram_id = $1
            """,
            telegram_id
        )
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С ИМЕНЕМ И ФАМИЛИЕЙ
# ============================================================================

async def update_user_name(telegram_id: int, first_name: str, last_name: str):
    """
    Сохраняет имя и фамилию пользователя в БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
        first_name (str): Имя пользователя
        last_name (str): Фамилия пользователя
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            UPDATE users 
            SET first_name = $1, last_name = $2 
            WHERE telegram_id = $3
            """,
            first_name, last_name, telegram_id
        )
    finally:
        await conn.close()


async def get_user_name(telegram_id: int):
    """
    Получает имя, фамилию и код пользователя из БД.
    
    Args:
        telegram_id (int): ID пользователя в Telegram
    
    Returns:
        asyncpg.Record: Запись с полями first_name, last_name, user_code
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT first_name, last_name, user_code 
            FROM users 
            WHERE telegram_id = $1
            """,
            telegram_id
        )
        return row if row else None
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С ЧАТАМИ
# ============================================================================

async def create_chat(client_id: int, provider_id: int):
    """
    Создаёт новый чат между клиентом и мастером.
    
    Args:
        client_id (int): ID клиента в Telegram
        provider_id (int): ID мастера в Telegram
    
    Returns:
        int: ID созданного чата
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO chats (client_telegram_id, provider_telegram_id)
            VALUES ($1, $2) RETURNING id
            """,
            client_id, provider_id
        )
        return row["id"]
    finally:
        await conn.close()


async def get_active_chat_by_client(client_id: int):
    """
    Получает активный чат для клиента.
    
    Args:
        client_id (int): ID клиента в Telegram
    
    Returns:
        asyncpg.Record: Запись чата или None, если активного чата нет
    """
    conn = await get_db_connection()
    try:
        return await conn.fetchrow(
            """
            SELECT * FROM chats 
            WHERE client_telegram_id = $1 AND is_active = true
            """,
            client_id
        )
    finally:
        await conn.close()


async def get_active_chat_by_provider(provider_id: int):
    """
    Получает активный чат для мастера.
    
    Args:
        provider_id (int): ID мастера в Telegram
    
    Returns:
        asyncpg.Record: Запись чата или None, если активного чата нет
    """
    conn = await get_db_connection()
    try:
        return await conn.fetchrow(
            """
            SELECT * FROM chats 
            WHERE provider_telegram_id = $1 AND is_active = true
            """,
            provider_id
        )
    finally:
        await conn.close()


async def close_chat(chat_id: int):
    """
    Завершает чат (устанавливает is_active = false).
    
    Args:
        chat_id (int): ID чата для завершения
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE chats SET is_active = false WHERE id = $1", 
            chat_id
        )
    finally:
        await conn.close()


async def get_user_telegram_id_by_code(user_code: str):
    """
    Получает telegram_id по 6-значному коду пользователя.
    
    Args:
        user_code (str): 6-значный код пользователя
    
    Returns:
        int: telegram_id или None, если пользователь не найден
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE user_code = $1", 
            user_code
        )
        return row["telegram_id"] if row else None
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С ЗАПИСЯМИ НА УСЛУГИ
# ============================================================================

async def create_service_record(
    provider_id: int, 
    client_id: int, 
    service_name: str, 
    cost: int, 
    address: str, 
    date: date_type, 
    time: datetime, 
    comments: str
):
    """
    Создаёт новую запись на услугу в БД.
    
    Args:
        provider_id (int): ID мастера
        client_id (int): ID клиента
        service_name (str): Название услуги
        cost (int): Стоимость в рублях
        address (str): Адрес проведения услуги
        date (date): Дата услуги
        time (time): Время услуги
        comments (str): Комментарии
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO service_records 
            (provider_telegram_id, client_telegram_id, service_name, cost, 
             address, service_date, service_time, comments, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active')
            """,
            provider_id, client_id, service_name, cost, 
            address, date, time, comments
        )
    finally:
        await conn.close()


async def get_record_years(telegram_id: int, role: str) -> list[int]:
    """
    Получает список лет с записями для пользователя.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'provider' или 'client'
    
    Returns:
        list[int]: Список лет (например, [2025, 2026])
    """
    conn = await get_db_connection()
    try:
        if role == "provider":
            query = """
                SELECT DISTINCT EXTRACT(YEAR FROM service_date) 
                FROM service_records 
                WHERE provider_telegram_id = $1 
                  AND status != 'completed'
                ORDER BY 1 DESC
            """
        else:  # client
            query = """
                SELECT DISTINCT EXTRACT(YEAR FROM service_date) 
                FROM service_records 
                WHERE client_telegram_id = $1 
                  AND status != 'completed'
                ORDER BY 1 DESC
            """
        
        rows = await conn.fetch(query, telegram_id)
        return [int(row[0]) for row in rows if row[0]]
    finally:
        await conn.close()


async def get_record_months(telegram_id: int, role: str, year: int) -> dict[int, int]:
    """
    Получает количество записей по месяцам для заданного года.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'provider' или 'client'
        year (int): Год для фильтрации
    
    Returns:
        dict[int, int]: Словарь {номер_месяца: количество_записей}
    """
    conn = await get_db_connection()
    try:
        if role == "provider":
            query = """
                SELECT EXTRACT(MONTH FROM service_date), COUNT(*)
                FROM service_records
                WHERE provider_telegram_id = $1 
                  AND EXTRACT(YEAR FROM service_date) = $2
                  AND status != 'completed'
                GROUP BY EXTRACT(MONTH FROM service_date)
            """
        else:  # client
            query = """
                SELECT EXTRACT(MONTH FROM service_date), COUNT(*)
                FROM service_records
                WHERE client_telegram_id = $1 
                  AND EXTRACT(YEAR FROM service_date) = $2
                  AND status != 'completed'
                GROUP BY EXTRACT(MONTH FROM service_date)
            """
        
        rows = await conn.fetch(query, telegram_id, year)
        return {int(row[0]): int(row[1]) for row in rows if row[0]}
    finally:
        await conn.close()


async def get_record_days(telegram_id: int, role: str, year: int, month: int) -> dict[int, int]:
    """
    Получает количество записей по дням для заданного месяца.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'provider' или 'client'
        year (int): Год
        month (int): Месяц (1-12)
    
    Returns:
        dict[int, int]: Словарь {день_месяца: количество_записей}
    """
    conn = await get_db_connection()
    try:
        if role == "provider":
            query = """
                SELECT EXTRACT(DAY FROM service_date), COUNT(*)
                FROM service_records
                WHERE provider_telegram_id = $1 
                  AND EXTRACT(YEAR FROM service_date) = $2
                  AND EXTRACT(MONTH FROM service_date) = $3
                  AND status != 'completed'
                GROUP BY EXTRACT(DAY FROM service_date)
            """
        else:  # client
            query = """
                SELECT EXTRACT(DAY FROM service_date), COUNT(*)
                FROM service_records
                WHERE client_telegram_id = $1 
                  AND EXTRACT(YEAR FROM service_date) = $2
                  AND EXTRACT(MONTH FROM service_date) = $3
                  AND status != 'completed'
                GROUP BY EXTRACT(DAY FROM service_date)
            """
        
        rows = await conn.fetch(query, telegram_id, year, month)
        return {int(row[0]): int(row[1]) for row in rows if row[0]}
    finally:
        await conn.close()


async def get_records_by_date(telegram_id: int, role: str, year: int, month: int, day: int):
    """
    Получает все записи на конкретную дату.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'provider' или 'client'
        year (int): Год
        month (int): Месяц
        day (int): День
    
    Returns:
        list[asyncpg.Record]: Список записей на эту дату
    """
    conn = await get_db_connection()
    try:
        target_date = date_type(year, month, day)
        
        if role == "provider":
            query = """
                SELECT service_name, cost, address, service_time, comments, client_telegram_id
                FROM service_records
                WHERE provider_telegram_id = $1 
                  AND service_date = $2
                  AND status != 'completed'
                ORDER BY service_time
            """
        else:  # client
            query = """
                SELECT service_name, cost, address, service_time, comments
                FROM service_records
                WHERE client_telegram_id = $1 
                  AND service_date = $2
                  AND status != 'completed'
                ORDER BY service_time
            """
        
        return await conn.fetch(query, telegram_id, target_date)
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С УВЕДОМЛЕНИЯМИ
# ============================================================================

async def create_notification(telegram_id: int, role: str, message_text: str):
    """
    Создаёт уведомление для пользователя определённой роли.
    
    Args:
        telegram_id (int): ID получателя
        role (str): 'client' или 'provider'
        message_text (str): Текст уведомления
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO notifications (user_telegram_id, role, message_text)
            VALUES ($1, $2, $3)
            """,
            telegram_id, role, message_text
        )
    finally:
        await conn.close()


async def get_unread_count(telegram_id: int, role: str) -> int:
    """
    Получает количество непрочитанных уведомлений для пользователя и роли.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'client' или 'provider'
    
    Returns:
        int: Количество непрочитанных уведомлений
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) FROM notifications
            WHERE user_telegram_id = $1 AND role = $2 AND is_read = false
            """,
            telegram_id, role
        )
        return row[0] if row else 0
    finally:
        await conn.close()


async def mark_notifications_as_read(telegram_id: int, role: str):
    """
    Помечает все уведомления пользователя как прочитанные.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'client' или 'provider'
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            UPDATE notifications
            SET is_read = true
            WHERE user_telegram_id = $1 AND role = $2 AND is_read = false
            """,
            telegram_id, role
        )
    finally:
        await conn.close()


async def get_unread_notifications(telegram_id: int, role: str):
    """
    Получает список непрочитанных уведомлений.
    
    Args:
        telegram_id (int): ID пользователя
        role (str): 'client' или 'provider'
    
    Returns:
        list[asyncpg.Record]: Список уведомлений с полями message_text, created_at
    """
    conn = await get_db_connection()
    try:
        return await conn.fetch(
            """
            SELECT message_text, created_at
            FROM notifications
            WHERE user_telegram_id = $1 AND role = $2 AND is_read = false
            ORDER BY created_at
            """,
            telegram_id, role
        )
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ ОТМЕНЫ И ЗАВЕРШЕНИЯ ЗАПИСЕЙ
# ============================================================================

async def cancel_service_record(record_id: int, provider_id: int):
    """
    Отменяет запись на услугу (только для своего мастера).
    
    Args:
        record_id (int): ID записи
        provider_id (int): ID мастера
    
    Returns:
        bool: True если запись успешно отменена, иначе False
    """
    conn = await get_db_connection()
    try:
        result = await conn.execute(
            """
            UPDATE service_records 
            SET status = 'cancelled', cancelled_at = NOW()
            WHERE id = $1 AND provider_telegram_id = $2 AND status = 'active'
            """,
            record_id, provider_id
        )
        return result.split()[1] == '1'
    finally:
        await conn.close()


async def complete_service(record_id: int, provider_id: int, duration_minutes: int, rating: bool, notes: str):
    """
    Завершает услугу и сохраняет результат в БД.
    
    Args:
        record_id (int): ID записи
        provider_id (int): ID мастера
        duration_minutes (int): Длительность услуги в минутах
        rating (bool): Оценка (True = хорошо, False = плохо)
        notes (str): Комментарии
    
    Returns:
        bool: True если услуга успешно завершена, иначе False
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT id FROM service_records 
            WHERE id = $1 AND provider_telegram_id = $2 AND status = 'active'
            """,
            record_id, provider_id
        )
        if not row:
            return False
        
        await conn.execute(
            """
            UPDATE service_records SET status = 'completed' WHERE id = $1
            """,
            record_id
        )
        
        return True
    finally:
        await conn.close()


async def get_active_records_for_provider(provider_id: int):
    """
    Получает все активные записи мастера для отмены/завершения.
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        list[asyncpg.Record]: Список активных записей
    """
    conn = await get_db_connection()
    try:
        return await conn.fetch(
            """
            SELECT id, service_name, service_date, service_time, client_telegram_id
            FROM service_records
            WHERE provider_telegram_id = $1 AND status = 'active'
            ORDER BY service_date, service_time
            """,
            provider_id
        )
    finally:
        await conn.close()


async def get_client_from_record(record_id: int):
    """
    Получает ID клиента из записи на услугу.
    
    Args:
        record_id (int): ID записи
    
    Returns:
        int: ID клиента или None, если запись не найдена
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT client_telegram_id FROM service_records WHERE id = $1
            """,
            record_id
        )
        return row['client_telegram_id'] if row else None
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ УЧЁТА ТРАТ И СТАТИСТИКИ
# ============================================================================

async def add_expense(provider_id: int, amount: int, description: str):
    """
    Добавляет новую трату мастера в БД.
    
    Args:
        provider_id (int): ID мастера
        amount (int): Сумма траты в рублях
        description (str): Описание траты
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO expenses (provider_telegram_id, amount, description)
            VALUES ($1, $2, $3)
            """,
            provider_id, amount, description
        )
    finally:
        await conn.close()


async def get_statistics(provider_id: int, period: str, tax_rate: float = 4.0):
    """
    Рассчитывает статистику для мастера за указанный период.
    
    Args:
        provider_id (int): ID мастера
        period (str): 'day', 'week' или 'month'
        tax_rate (float): Налоговая ставка в процентах
    
    Returns:
        dict: Словарь с ключами income, expenses, tax, net, period, tax_updated
    """
    conn = await get_db_connection()
    try:
        now = datetime.now().date()
        
        if period == 'day':
            start_date = now
            income_query = """
                SELECT COALESCE(SUM(cost), 0) as total
                FROM service_records
                WHERE provider_telegram_id = $1 
                  AND status = 'completed'
                  AND service_date = $2
            """
        elif period == 'week':
            start_date = now - timedelta(days=7)
            income_query = """
                SELECT COALESCE(SUM(cost), 0) as total
                FROM service_records
                WHERE provider_telegram_id = $1 
                  AND status = 'completed'
                  AND service_date >= $2
            """
        else:  # month
            start_date = now.replace(day=1)
            income_query = """
                SELECT COALESCE(SUM(cost), 0) as total
                FROM service_records
                WHERE provider_telegram_id = $1 
                  AND status = 'completed'
                  AND service_date >= $2
            """
        
        income_row = await conn.fetchrow(income_query, provider_id, start_date)
        income = income_row['total']
        
        expense_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE provider_telegram_id = $1 AND created_at::date >= $2
            """,
            provider_id, start_date
        )
        expenses = expense_row['total']
        
        tax = int(income * (tax_rate / 100))
        net = income - tax - expenses
        
        tax_updated_row = await conn.fetchrow(
            """
            SELECT updated_at FROM tax_rates WHERE tax_type = 'npd_individual'
            """
        )
        tax_updated = tax_updated_row['updated_at'] if tax_updated_row else datetime.now()
        
        return {
            'income': income,
            'expenses': expenses,
            'tax': tax,
            'net': net,
            'period': period,
            'tax_updated': tax_updated
        }
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ КАЛЕНДАРЯ И ПРОВЕРКИ ЗАПИСЕЙ
# ============================================================================

async def get_records_by_date_for_provider(provider_id: int, year: int, month: int, day: int):
    """
    Получает записи мастера на конкретную дату (для отображения при создании новой записи).
    
    Используется в handlers/service_record.py для показа занятого времени.
    
    Args:
        provider_id (int): ID мастера
        year (int): Год
        month (int): Месяц (1-12)
        day (int): День месяца
    
    Returns:
        list[asyncpg.Record]: Список записей с полями service_time, service_name
    """
    conn = await get_db_connection()
    try:
        target_date = date_type(year, month, day)
        query = """
            SELECT service_time, service_name
            FROM service_records
            WHERE provider_telegram_id = $1 
              AND service_date = $2
              AND status != 'completed'
            ORDER BY service_time
        """
        return await conn.fetch(query, provider_id, target_date)
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ СИСТЕМЫ ЗАПРОСОВ ПОВТОРНОЙ ЗАПИСИ
# ============================================================================

async def get_client_providers_for_repeat(client_id: int):
    """
    Получает список уникальных мастеров, к которым клиент записывался.
    
    Args:
        client_id (int): ID клиента
    
    Returns:
        list[dict]: Список мастеров с услугами и количеством записей
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.telegram_id as provider_id,
                u.first_name,
                u.last_name,
                u.user_code,
                COUNT(DISTINCT sr.service_name) as service_count,
                COUNT(sr.id) as total_records,
                STRING_AGG(DISTINCT sr.service_name, ', ') as services_list
            FROM service_records sr
            JOIN users u ON sr.provider_telegram_id = u.telegram_id
            WHERE sr.client_telegram_id = $1 
              AND sr.status = 'completed'
            GROUP BY u.telegram_id, u.first_name, u.last_name, u.user_code
            ORDER BY total_records DESC
            """,
            client_id
        )
        
        result = []
        for row in rows:
            full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
            result.append({
                'provider_id': row['provider_id'],
                'full_name': full_name,
                'user_code': row['user_code'],
                'service_count': row['service_count'],
                'total_records': row['total_records'],
                'services_list': row['services_list']
            })
        
        return result
    
    finally:
        await conn.close()


async def search_providers_for_repeat(client_id: int, query: str, search_type: str):
    """
    Поиск мастеров по услуге или имени.
    
    Args:
        client_id (int): ID клиента
        query (str): Поисковый запрос
        search_type (str): 'service' или 'name'
    
    Returns:
        list[dict]: Список найденных мастеров
    """
    conn = await get_db_connection()
    try:
        if search_type == 'service':
            rows = await conn.fetch(
                """
                SELECT 
                    u.telegram_id as provider_id,
                    u.first_name,
                    u.last_name,
                    u.user_code,
                    COUNT(sr.id) as total_records,
                    STRING_AGG(DISTINCT sr.service_name, ', ') as services_list
                FROM service_records sr
                JOIN users u ON sr.provider_telegram_id = u.telegram_id
                WHERE sr.client_telegram_id = $1 
                  AND sr.status = 'completed'
                  AND LOWER(sr.service_name) LIKE LOWER($2)
                GROUP BY u.telegram_id, u.first_name, u.last_name, u.user_code
                ORDER BY total_records DESC
                """,
                client_id,
                f"%{query}%"
            )
        else:  # search_type == 'name'
            rows = await conn.fetch(
                """
                SELECT 
                    u.telegram_id as provider_id,
                    u.first_name,
                    u.last_name,
                    u.user_code,
                    COUNT(sr.id) as total_records,
                    STRING_AGG(DISTINCT sr.service_name, ', ') as services_list
                FROM service_records sr
                JOIN users u ON sr.provider_telegram_id = u.telegram_id
                WHERE sr.client_telegram_id = $1 
                  AND sr.status = 'completed'
                  AND (
                    LOWER(u.first_name) LIKE LOWER($2) OR
                    LOWER(u.last_name) LIKE LOWER($2)
                  )
                GROUP BY u.telegram_id, u.first_name, u.last_name, u.user_code
                ORDER BY total_records DESC
                """,
                client_id,
                f"%{query}%"
            )
        
        result = []
        for row in rows:
            full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
            result.append({
                'provider_id': row['provider_id'],
                'full_name': full_name,
                'user_code': row['user_code'],
                'total_records': row['total_records'],
                'services_list': row['services_list']
            })
        
        return result
    
    finally:
        await conn.close()


async def create_repeat_request(client_id: int, provider_id: int, service_name: str = None):
    """
    Создаёт новый запрос на повторную запись.
    
    Args:
        client_id (int): ID клиента
        provider_id (int): ID мастера
        service_name (str, optional): Название услуги
    
    Returns:
        int: ID созданного запроса
    """
    conn = await get_db_connection()
    try:
        provider_info = await conn.fetchrow(
            "SELECT first_name, last_name FROM users WHERE telegram_id = $1",
            provider_id
        )
        
        row = await conn.fetchrow(
            """
            INSERT INTO repeat_requests 
            (client_telegram_id, provider_telegram_id, service_name, provider_first_name, provider_last_name)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            client_id,
            provider_id,
            service_name,
            provider_info['first_name'] if provider_info else None,
            provider_info['last_name'] if provider_info else None
        )
        
        return row['id']
    
    finally:
        await conn.close()


async def get_pending_requests_for_provider(provider_id: int):
    """
    Получает список НОВЫХ запросов для мастера с полной диагностикой.
    """
    conn = await get_db_connection()
    try:
        # ДИАГНОСТИКА: Логируем входящий ID
        import logging
        logging.info(f"🔍 Запрос запросов для мастера ID: {provider_id} (тип: {type(provider_id)})")
        
        # Проверка 1: Существует ли пользователь с таким ID?
        user_exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE telegram_id = $1::BIGINT",
            provider_id
        )
        logging.info(f"👤 Пользователь существует: {'Да' if user_exists else 'Нет'}")
        
        # Проверка 2: Есть ли вообще какие-либо запросы в таблице?
        total_requests = await conn.fetchval("SELECT COUNT(*) FROM repeat_requests")
        logging.info(f"📊 Всего запросов в таблице: {total_requests}")
        
        # Проверка 3: Есть ли запросы с любым provider_telegram_id?
        any_provider_requests = await conn.fetchval(
            "SELECT COUNT(*) FROM repeat_requests WHERE provider_telegram_id IS NOT NULL"
        )
        logging.info(f"📊 Запросов с заполненным provider_telegram_id: {any_provider_requests}")
        
        # Основной запрос с явным приведением типов
        rows = await conn.fetch(
            """
            SELECT 
                rr.id as request_id,
                rr.client_telegram_id,
                rr.service_name,
                rr.created_at,
                rr.status,
                u.first_name as client_first_name,
                u.last_name as client_last_name,
                u.user_code as client_code
            FROM repeat_requests rr
            LEFT JOIN users u ON rr.client_telegram_id = u.telegram_id
            WHERE CAST(rr.provider_telegram_id AS BIGINT) = $1::BIGINT 
              AND rr.status = 'pending'
            ORDER BY rr.created_at DESC
            """,
            provider_id
        )
        
        logging.info(f"✅ Найдено запросов для мастера {provider_id}: {len(rows)}")
        
        # Детальный лог каждой записи
        for i, row in enumerate(rows):
            logging.info(
                f"  Запись {i+1}: ID={row['request_id']}, "
                f"client_id={row['client_telegram_id']}, "
                f"status={row['status']}"
            )
        
        result = []
        for row in rows:
            client_name = f"{row['client_first_name'] or ''} {row['client_last_name'] or ''}".strip() or "Клиент"
            result.append({
                'request_id': row['request_id'],
                'client_id': row['client_telegram_id'],
                'client_name': client_name,
                'client_code': row['client_code'] or "???",
                'service_name': row['service_name'] or "Не указана",
                'created_at': row['created_at'],
                'message_count': 0  # Будет заполнено отдельно
            })
        
        return result
    
    except Exception as e:
        logging.error(f"❌ Ошибка в get_pending_requests_for_provider: {e}", exc_info=True)
        raise
    finally:
        await conn.close()

async def get_all_client_requests(client_id: int):
    """
    Получает ВСЕ запросы клиента (для истории).
    
    ИСПРАВЛЕНО: Явное приведение client_id к BIGINT в SQL-запросе.
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                rr.id as request_id,
                rr.provider_telegram_id,
                rr.service_name,
                rr.created_at,
                rr.status,
                u.first_name as provider_first_name,
                u.last_name as provider_last_name,
                u.user_code as provider_code,
                (SELECT COUNT(*) FROM request_messages WHERE request_id = rr.id) as message_count
            FROM repeat_requests rr
            JOIN users u ON rr.provider_telegram_id = u.telegram_id
            WHERE rr.client_telegram_id = $1::BIGINT 
            ORDER BY rr.created_at DESC
            """,
            client_id
        )
        
        result = []
        for row in rows:
            provider_name = f"{row['provider_first_name'] or ''} {row['provider_last_name'] or ''}".strip() or "Мастер"
            
            status_map = {
                'pending': '⏳ Ожидает ответа',
                'accepted': '✅ Принят',
                'rejected': '❌ Отклонён',
                'completed': '✔️ Завершён'
            }
            status_text = status_map.get(row['status'], f"Статус: {row['status']}")
            
            result.append({
                'request_id': row['request_id'],
                'provider_id': row['provider_telegram_id'],
                'provider_name': provider_name,
                'provider_code': row['provider_code'],
                'service_name': row['service_name'] or "Не указана",
                'status': status_text,
                'created_at': row['created_at'],
                'message_count': row['message_count']
            })
        
        return result
    
    finally:
        await conn.close()


async def get_pending_requests_for_client(client_id: int):
    """
    Получает список ВСЕХ запросов клиента (включая завершённые для истории).
    
    ИСПРАВЛЕНО: Убран фильтр по статусу 'pending'/'accepted' — клиент должен видеть
    все свои запросы для истории, включая отклонённые и завершённые.
    
    Args:
        client_id (int): ID клиента
    
    Returns:
        list[dict]: Список запросов с информацией о мастере
    """
    conn = await get_db_connection()
    try:
        # ИСПРАВЛЕНО: Убрано условие "AND rr.status IN ('pending', 'accepted')"
        # Клиент должен видеть ВСЕ свои запросы для истории
        rows = await conn.fetch(
            """
            SELECT 
                rr.id as request_id,
                rr.provider_telegram_id,
                rr.service_name,
                rr.created_at,
                rr.status,
                u.first_name as provider_first_name,
                u.last_name as provider_last_name,
                u.user_code as provider_code,
                (SELECT COUNT(*) FROM request_messages WHERE request_id = rr.id) as message_count
            FROM repeat_requests rr
            JOIN users u ON rr.provider_telegram_id = u.telegram_id
            WHERE rr.client_telegram_id = $1 
            ORDER BY rr.created_at DESC
            """,
            client_id
        )
        
        result = []
        for row in rows:
            provider_name = f"{row['provider_first_name'] or ''} {row['provider_last_name'] or ''}".strip() or "Мастер"
            
            # ИСПРАВЛЕНО: Расширенные статусы для лучшей визуализации
            status_map = {
                'pending': '⏳ Ожидает ответа',
                'accepted': '✅ Принят',
                'rejected': '❌ Отклонён',
                'completed': '✔️ Завершён'
            }
            status_text = status_map.get(row['status'], f"Статус: {row['status']}")
            
            result.append({
                'request_id': row['request_id'],
                'provider_id': row['provider_telegram_id'],
                'provider_name': provider_name,
                'provider_code': row['provider_code'],
                'service_name': row['service_name'] or "Не указана",
                'status': status_text,
                'created_at': row['created_at'],
                'message_count': row['message_count']
            })
        
        return result
    
    finally:
        await conn.close()


async def add_request_message(request_id: int, sender_role: str, sender_id: int, message_text: str, photo_file_id: str = None):
    """
    Добавляет сообщение в диалог запроса.
    
    Args:
        request_id (int): ID запроса
        sender_role (str): 'client' или 'provider'
        sender_id (int): ID отправителя
        message_text (str): Текст сообщения
        photo_file_id (str, optional): ID фото в Telegram
    
    Returns:
        int: ID созданного сообщения
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO request_messages 
            (request_id, sender_role, sender_telegram_id, message_text, photo_file_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            request_id,
            sender_role,
            sender_id,
            message_text,
            photo_file_id
        )
        
        await conn.execute(
            """
            UPDATE repeat_requests 
            SET updated_at = NOW() 
            WHERE id = $1
            """,
            request_id
        )
        
        return row['id']
    
    finally:
        await conn.close()


async def get_request_messages(request_id: int):
    """
    Получает все сообщения в диалоге запроса.
    
    Args:
        request_id (int): ID запроса
    
    Returns:
        list[dict]: Список сообщений с информацией об отправителе
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                rm.*,
                u.first_name,
                u.last_name,
                u.user_code
            FROM request_messages rm
            JOIN users u ON rm.sender_telegram_id = u.telegram_id
            WHERE rm.request_id = $1
            ORDER BY rm.sent_at ASC
            """,
            request_id
        )
        
        result = []
        for row in rows:
            sender_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Пользователь"
            result.append({
                'message_id': row['id'],
                'sender_role': row['sender_role'],
                'sender_name': sender_name,
                'sender_code': row['user_code'],
                'message_text': row['message_text'],
                'photo_file_id': row['photo_file_id'],
                'sent_at': row['sent_at']
            })
        
        return result
    
    finally:
        await conn.close()


async def accept_repeat_request(request_id: int, provider_id: int):
    """
    Принимает запрос на повторную запись.
    
    Args:
        request_id (int): ID запроса
        provider_id (int): ID мастера
    
    Returns:
        bool: True если запрос принят успешно
    """
    conn = await get_db_connection()
    try:
        result = await conn.execute(
            """
            UPDATE repeat_requests 
            SET status = 'accepted', updated_at = NOW()
            WHERE id = $1 AND provider_telegram_id = $2 AND status = 'pending'
            """,
            request_id,
            provider_id
        )
        return result.split()[1] == '1'
    
    finally:
        await conn.close()


async def reject_repeat_request(request_id: int, provider_id: int):
    """
    Отклоняет запрос на повторную запись.
    
    Args:
        request_id (int): ID запроса
        provider_id (int): ID мастера
    
    Returns:
        bool: True если запрос отклонён успешно
    """
    conn = await get_db_connection()
    try:
        result = await conn.execute(
            """
            UPDATE repeat_requests 
            SET status = 'rejected', updated_at = NOW()
            WHERE id = $1 AND provider_telegram_id = $2 AND status = 'pending'
            """,
            request_id,
            provider_id
        )
        return result.split()[1] == '1'
    
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ ГЕОКОДИРОВАНИЯ И РАСЧЁТА РАССТОЯНИЯ
# ============================================================================

from math import radians, sin, cos, sqrt, atan2
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import asyncio

# Глобальный геокодер (с кэшированием для уменьшения запросов)
_geolocator = Nominatim(user_agent="secretariat_bot")
_geocode_cache = {}  # Кэш: адрес → (широта, долгота)

async def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Преобразует адрес в координаты (широта, долгота)
    
    Использует кэширование для уменьшения количества запросов к Nominatim.
    Лимит: 1 запрос/сек (требование Nominatim).
    
    Args:
        address (str): Адрес для геокодирования
    
    Returns:
        tuple[float, float] | None: (широта, долгота) или None при ошибке
    """
    # Проверяем кэш
    if address in _geocode_cache:
        return _geocode_cache[address]
    
    try:
        # Асинхронный вызов геокодера (обёртка над синхронным вызовом)
        loop = asyncio.get_event_loop()
        location = await loop.run_in_executor(None, _geolocator.geocode, address)
        
        if location:
            coords = (float(location.latitude), float(location.longitude))
            _geocode_cache[address] = coords  # Сохраняем в кэш
            return coords
        return None
    
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning(f"Ошибка геокодирования адреса '{address}': {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка геокодирования: {e}")
        return None


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Рассчитывает расстояние между двумя точками по формуле Хаверсина
    
    Args:
        lat1 (float): Широта точки 1
        lon1 (float): Долгота точки 1
        lat2 (float): Широта точки 2
        lon2 (float): Долгота точки 2
    
    Returns:
        float: Расстояние в километрах
    """
    # Радиус Земли в км
    R = 6371.0
    
    # Преобразуем градусы в радианы
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Разница координат
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Формула Хаверсина
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c


# ============================================================================
# ФУНКЦИИ РАБОТЫ С АДРЕСАМИ МАСТЕРОВ
# ============================================================================

async def search_nearby_providers(client_address: str, service_query: str, limit: int = 10):
    """
    Ищет ближайших мастеров по адресу клиента и названию услуги
    
    Алгоритм поиска:
    1. Геокодируем адрес клиента → получаем координаты
    2. Ищем мастеров с услугами:
       а) Точное совпадение названия (регистронезависимое)
       б) Совпадение по словам (полнотекстовый поиск)
    3. Рассчитываем расстояние до каждого мастера
    4. Сортируем по расстоянию, возвращаем топ-10
    
    Args:
        client_address (str): Адрес клиента для поиска
        service_query (str): Название услуги для поиска
        limit (int): Максимальное количество результатов
    
    Returns:
        list[dict]: Список мастеров с расстоянием и услугами
    """
    # Шаг 1: Геокодируем адрес клиента
    client_coords = await geocode_address(client_address)
    if not client_coords:
        raise ValueError(f"Не удалось определить координаты для адреса: {client_address}")
    
    client_lat, client_lon = client_coords
    
    # Шаг 2: Получаем всех мастеров с подходящими услугами
    conn = await get_db_connection()
    try:
        # Сначала ищем точное совпадение
        exact_match_query = """
            SELECT DISTINCT u.telegram_id, u.first_name, u.last_name, u.user_code,
                   pa.address, pa.latitude, pa.longitude,
                   ps.service_name, ps.description, ps.price_range
            FROM users u
            JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
            JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
            WHERE LOWER(ps.service_name) = LOWER($1)
              AND pa.latitude IS NOT NULL 
              AND pa.longitude IS NOT NULL
        """
        
        # Затем ищем по словам (полнотекстовый поиск)
        fuzzy_match_query = """
            SELECT DISTINCT u.telegram_id, u.first_name, u.last_name, u.user_code,
                   pa.address, pa.latitude, pa.longitude,
                   ps.service_name, ps.description, ps.price_range
            FROM users u
            JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
            JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
            WHERE to_tsvector('russian', ps.service_name || ' ' || COALESCE(ps.description, ''))
                  @@ to_tsquery('russian', replace($1, ' ', ' & '))
              AND pa.latitude IS NOT NULL 
              AND pa.longitude IS NOT NULL
              AND u.telegram_id NOT IN (
                  SELECT DISTINCT u2.telegram_id
                  FROM users u2
                  JOIN provider_services ps2 ON u2.telegram_id = ps2.provider_telegram_id
                  WHERE LOWER(ps2.service_name) = LOWER($1)
              )
        """
        
        # Выполняем оба запроса
        exact_rows = await conn.fetch(exact_match_query, service_query)
        fuzzy_rows = await conn.fetch(fuzzy_match_query, service_query)
        
        # Объединяем результаты (сначала точные совпадения)
        all_rows = list(exact_rows) + list(fuzzy_rows)
        
        if not all_rows:
            return []  # Нет мастеров с такими услугами
        
        # Шаг 3: Рассчитываем расстояние и сортируем
        providers_with_distance = []
        seen_providers = set()  # Для избежания дубликатов
        
        for row in all_rows:
            provider_id = row['telegram_id']
            
            # Пропускаем дубликаты
            if provider_id in seen_providers:
                continue
            seen_providers.add(provider_id)
            
            # Рассчитываем расстояние
            distance = calculate_distance(
                client_lat,
                client_lon,
                float(row['latitude']),
                float(row['longitude'])
            )
            
            # Формируем данные мастера
            full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
            
            providers_with_distance.append({
                'provider_id': provider_id,
                'full_name': full_name,
                'user_code': row['user_code'],
                'address': row['address'],
                'distance_km': round(distance, 1),
                'service_name': row['service_name'],
                'description': row['description'],
                'price_range': row['price_range']
            })
        
        # Сортируем по расстоянию
        providers_with_distance.sort(key=lambda x: x['distance_km'])
        
        # Возвращаем топ-N
        return providers_with_distance[:limit]
    
    finally:
        await conn.close()


async def get_provider_addresses(provider_id: int):
    """
    Получает все адреса мастера
    
    Returns:
        list[dict]: Список адресов с координатами
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, address, latitude, longitude, is_primary, created_at
            FROM provider_addresses
            WHERE provider_telegram_id = $1
            ORDER BY is_primary DESC, created_at DESC
            """,
            provider_id
        )
        return [
            {
                'id': row['id'],
                'address': row['address'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'is_primary': row['is_primary'],
                'created_at': row['created_at']
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def delete_provider_address(address_id: int, provider_id: int):
    """
    Удаляет адрес мастера (только свой)
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            DELETE FROM provider_addresses 
            WHERE id = $1 AND provider_telegram_id = $2
            """,
            address_id, provider_id
        )
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С УСЛУГАМИ МАСТЕРОВ
# ============================================================================

async def add_provider_service(provider_id: int, service_name: str, description: str = None, price_range: str = None):
    """
    Добавляет услугу для мастера
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO provider_services 
            (provider_telegram_id, service_name, description, price_range)
            VALUES ($1, $2, $3, $4)
            """,
            provider_id, service_name.strip(), description, price_range
        )
    finally:
        await conn.close()


async def get_provider_services(provider_id: int):
    """
    Получает все услуги мастера
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, service_name, description, price_range, created_at
            FROM provider_services
            WHERE provider_telegram_id = $1
            ORDER BY created_at DESC
            """,
            provider_id
        )
        return [
            {
                'id': row['id'],
                'service_name': row['service_name'],
                'description': row['description'],
                'price_range': row['price_range'],
                'created_at': row['created_at']
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def delete_provider_service(service_id: int, provider_id: int):
    """
    Удаляет услугу мастера (только свою)
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            DELETE FROM provider_services 
            WHERE id = $1 AND provider_telegram_id = $2
            """,
            service_id, provider_id
        )
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИЯ ПОИСКА БЛИЖАЙШИХ МАСТЕРОВ
# ============================================================================

async def search_nearby_providers(client_address: str, service_query: str, limit: int = 10):
    """
    Ищет ближайших мастеров по адресу клиента и названию услуги
    
    Алгоритм поиска:
    1. Геокодируем адрес клиента → получаем координаты
    2. Ищем мастеров с услугами:
       а) Точное совпадение названия (регистронезависимое)
       б) Совпадение по словам (полнотекстовый поиск)
    3. Рассчитываем расстояние до каждого мастера
    4. Сортируем по расстоянию, возвращаем топ-10
    
    Args:
        client_address (str): Адрес клиента для поиска
        service_query (str): Название услуги для поиска
        limit (int): Максимальное количество результатов
    
    Returns:
        list[dict]: Список мастеров с расстоянием и услугами
    """
    # Шаг 1: Геокодируем адрес клиента
    client_coords = await geocode_address(client_address)
    if not client_coords:
        raise ValueError(f"Не удалось определить координаты для адреса: {client_address}")
    
    client_lat, client_lon = client_coords
    
    # Шаг 2: Получаем всех мастеров с подходящими услугами
    conn = None
    try:
        conn = await get_db_connection()
        
        # Сначала ищем точное совпадение
        exact_match_query = """
            SELECT DISTINCT u.telegram_id, u.first_name, u.last_name, u.user_code,
                   pa.address, pa.latitude, pa.longitude,
                   ps.service_name, ps.description, ps.price_range
            FROM users u
            JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
            JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
            WHERE LOWER(ps.service_name) = LOWER($1)
              AND pa.latitude IS NOT NULL 
              AND pa.longitude IS NOT NULL
        """
        
        # Затем ищем по словам (полнотекстовый поиск)
        fuzzy_match_query = """
            SELECT DISTINCT u.telegram_id, u.first_name, u.last_name, u.user_code,
                   pa.address, pa.latitude, pa.longitude,
                   ps.service_name, ps.description, ps.price_range
            FROM users u
            JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
            JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
            WHERE to_tsvector('russian', ps.service_name || ' ' || COALESCE(ps.description, ''))
                  @@ to_tsquery('russian', replace($1, ' ', ' & '))
              AND pa.latitude IS NOT NULL 
              AND pa.longitude IS NOT NULL
              AND u.telegram_id NOT IN (
                  SELECT DISTINCT u2.telegram_id
                  FROM users u2
                  JOIN provider_services ps2 ON u2.telegram_id = ps2.provider_telegram_id
                  WHERE LOWER(ps2.service_name) = LOWER($1)
              )
        """
        
        # Выполняем оба запроса
        exact_rows = await conn.fetch(exact_match_query, service_query)
        fuzzy_rows = await conn.fetch(fuzzy_match_query, service_query)
        
        # Объединяем результаты (сначала точные совпадения)
        all_rows = list(exact_rows) + list(fuzzy_rows)
        
        if not all_rows:
            return []  # Нет мастеров с такими услугами
        
        # Шаг 3: Рассчитываем расстояние и сортируем
        providers_with_distance = []
        seen_providers = set()  # Для избежания дубликатов
        
        for row in all_rows:
            provider_id = row['telegram_id']
            
            # Пропускаем дубликаты
            if provider_id in seen_providers:
                continue
            seen_providers.add(provider_id)
            
            # Рассчитываем расстояние (проверяем, что координаты не NULL)
            try:
                lat = float(row['latitude'])
                lon = float(row['longitude'])
                distance = calculate_distance(client_lat, client_lon, lat, lon)
            except (TypeError, ValueError) as e:
                logger.warning(f"Ошибка расчёта расстояния для мастера {provider_id}: {e}")
                continue
            
            # Формируем данные мастера
            full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
            
            providers_with_distance.append({
                'provider_id': provider_id,
                'full_name': full_name,
                'user_code': row['user_code'],
                'address': row['address'],
                'distance_km': round(distance, 1),
                'service_name': row['service_name'],
                'description': row['description'],
                'price_range': row['price_range']
            })
        
        # Сортируем по расстоянию
        providers_with_distance.sort(key=lambda x: x['distance_km'])
        
        # Возвращаем топ-N
        return providers_with_distance[:limit]
    
    except Exception as e:
        logger.error(f"Ошибка поиска ближайших мастеров: {e}")
        raise
    
    finally:
        if conn is not None:
            await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С АДРЕСАМИ МАСТЕРОВ
# ============================================================================

async def add_provider_address(provider_id: int, address: str, latitude: float = None, longitude: float = None, is_primary: bool = False):
    """
    Добавляет адрес работы для мастера
    
    Если координаты не указаны — выполняет геокодирование.
    
    Args:
        provider_id (int): ID мастера
        address (str): Адрес
        latitude (float, optional): Широта (если известна)
        longitude (float, optional): Долгота (если известна)
        is_primary (bool): Основной адрес для поиска
    """
    # Если координаты не переданы — геокодируем адрес
    if latitude is None or longitude is None:
        coords = await geocode_address(address)
        if coords:
            latitude, longitude = coords
        else:
            # Если геокодирование не удалось — сохраняем без координат
            latitude = longitude = None
    
    conn = await get_db_connection()
    try:
        # Если устанавливаем как основной — снимаем флаг с других адресов
        if is_primary:
            await conn.execute(
                """
                UPDATE provider_addresses 
                SET is_primary = false 
                WHERE provider_telegram_id = $1
                """,
                provider_id
            )
        
        # Добавляем новый адрес
        await conn.execute(
            """
            INSERT INTO provider_addresses 
            (provider_telegram_id, address, latitude, longitude, is_primary)
            VALUES ($1, $2, $3, $4, $5)
            """,
            provider_id, address, latitude, longitude, is_primary
        )
    finally:
        await conn.close()


async def get_provider_addresses(provider_id: int):
    """
    Получает все адреса мастера
    
    Returns:
        list[dict]: Список адресов с координатами
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, address, latitude, longitude, is_primary, created_at
            FROM provider_addresses
            WHERE provider_telegram_id = $1
            ORDER BY is_primary DESC, created_at DESC
            """,
            provider_id
        )
        return [
            {
                'id': row['id'],
                'address': row['address'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'is_primary': row['is_primary'],
                'created_at': row['created_at']
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def delete_provider_address(address_id: int, provider_id: int):
    """
    Удаляет адрес мастера (только свой)
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            DELETE FROM provider_addresses 
            WHERE id = $1 AND provider_telegram_id = $2
            """,
            address_id, provider_id
        )
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С УСЛУГАМИ МАСТЕРОВ
# ============================================================================

async def add_provider_service(provider_id: int, service_name: str, description: str = None, price_range: str = None):
    """
    Добавляет услугу для мастера
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO provider_services 
            (provider_telegram_id, service_name, description, price_range)
            VALUES ($1, $2, $3, $4)
            """,
            provider_id, service_name.strip(), description, price_range
        )
    finally:
        await conn.close()


async def get_provider_services(provider_id: int):
    """
    Получает все услуги мастера
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, service_name, description, price_range, created_at
            FROM provider_services
            WHERE provider_telegram_id = $1
            ORDER BY created_at DESC
            """,
            provider_id
        )
        return [
            {
                'id': row['id'],
                'service_name': row['service_name'],
                'description': row['description'],
                'price_range': row['price_range'],
                'created_at': row['created_at']
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def delete_provider_service(service_id: int, provider_id: int):
    """
    Удаляет услугу мастера (только свою)
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            DELETE FROM provider_services 
            WHERE id = $1 AND provider_telegram_id = $2
            """,
            service_id, provider_id
        )
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С ОТЗЫВАМИ И РЕЙТИНГАМИ
# ============================================================================

async def create_provider_review(provider_id: int, client_id: int, service_record_id: int, rating: int, comment: str = None):
    """
    Создаёт отзыв о мастере после завершения услуги
    
    Автоматически обновляет кэшированные значения рейтинга в таблице users.
    
    Args:
        provider_id (int): ID мастера
        client_id (int): ID клиента
        service_record_id (int): ID записи на услугу
        rating (int): Оценка от 1 до 5
        comment (str, optional): Текстовый комментарий
    """
    conn = await get_db_connection()
    try:
        # Создаём отзыв
        await conn.execute(
            """
            INSERT INTO provider_reviews 
            (provider_telegram_id, client_telegram_id, service_record_id, rating, comment)
            VALUES ($1, $2, $3, $4, $5)
            """,
            provider_id, client_id, service_record_id, rating, comment
        )
        
        # Обновляем кэшированные значения рейтинга
        await conn.execute(
            """
            UPDATE users u
            SET 
                average_rating = (
                    SELECT AVG(rating) 
                    FROM provider_reviews 
                    WHERE provider_telegram_id = $1
                ),
                review_count = (
                    SELECT COUNT(*) 
                    FROM provider_reviews 
                    WHERE provider_telegram_id = $1
                )
            WHERE telegram_id = $1
            """,
            provider_id
        )
    finally:
        await conn.close()


async def get_provider_reviews(provider_id: int, limit: int = 10):
    """
    Получает отзывы о мастере с информацией о клиентах
    
    Args:
        provider_id (int): ID мастера
        limit (int): Максимальное количество отзывов
    
    Returns:
        list[dict]: Список отзывов с рейтингом, комментарием и данными клиента
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                pr.rating,
                pr.comment,
                pr.created_at,
                u.first_name as client_first_name,
                u.last_name as client_last_name,
                u.user_code as client_code
            FROM provider_reviews pr
            JOIN users u ON pr.client_telegram_id = u.telegram_id
            WHERE pr.provider_telegram_id = $1
            ORDER BY pr.created_at DESC
            LIMIT $2
            """,
            provider_id, limit
        )
        
        return [
            {
                'rating': row['rating'],
                'comment': row['comment'] or 'Без комментария',
                'created_at': row['created_at'],
                'client_name': f"{row['client_first_name'] or ''} {row['client_last_name'] or ''}".strip() or "Клиент",
                'client_code': row['client_code']
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def get_provider_rating_summary(provider_id: int):
    """
    Получает сводку рейтинга мастера
    
    Возвращает среднюю оценку, количество отзывов и клиентскую базу (завершённые записи).
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        dict: Сводка с полями:
            - average_rating: средняя оценка (0.0 если нет отзывов)
            - review_count: количество отзывов
            - client_base: количество уникальных клиентов
            - completed_services: количество завершённых услуг
    """
    conn = await get_db_connection()
    try:
        # Получаем кэшированные значения из таблицы users
        row = await conn.fetchrow(
            """
            SELECT average_rating, review_count
            FROM users
            WHERE telegram_id = $1
            """,
            provider_id
        )
        
        average_rating = float(row['average_rating']) if row and row['average_rating'] else 0.0
        review_count = int(row['review_count']) if row and row['review_count'] else 0
        
        # Получаем клиентскую базу (уникальные клиенты)
        client_base_row = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT client_telegram_id) as unique_clients,
                COUNT(*) as completed_services
            FROM service_records
            WHERE provider_telegram_id = $1 AND status = 'completed'
            """,
            provider_id
        )
        
        unique_clients = int(client_base_row['unique_clients']) if client_base_row else 0
        completed_services = int(client_base_row['completed_services']) if client_base_row else 0
        
        return {
            'average_rating': average_rating,
            'review_count': review_count,
            'client_base': unique_clients,
            'completed_services': completed_services
        }
    
    finally:
        await conn.close()


# ============================================================================
# ФУНКЦИИ РАБОТЫ С ФОТО ПРОФИЛЯ
# ============================================================================

async def update_provider_profile_photo(provider_id: int, photo_file_id: str):
    """
    Обновляет фото профиля мастера
    
    Args:
        provider_id (int): ID мастера
        photo_file_id (str): file_id фотографии в Telegram
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            UPDATE users 
            SET profile_photo_file_id = $1 
            WHERE telegram_id = $2
            """,
            photo_file_id, provider_id
        )
    finally:
        await conn.close()


async def get_provider_profile_photo(provider_id: int):
    """
    Получает фото профиля мастера
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        str | None: file_id фотографии или None
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT profile_photo_file_id 
            FROM users 
            WHERE telegram_id = $1
            """,
            provider_id
        )
        return row['profile_photo_file_id'] if row else None
    finally:
        await conn.close()


# ============================================================================
# ОБНОВЛЁННАЯ ФУНКЦИЯ ПОИСКА С РЕЙТИНГОМ
# ============================================================================

async def search_nearby_providers_with_rating(client_address: str, service_query: str, limit: int = 10):
    """
    Расширенный поиск ближайших мастеров с рейтингом и статистикой
    
    Возвращает дополнительно:
    - Среднюю оценку мастера
    - Количество отзывов
    - Размер клиентской базы
    
    Args:
        client_address (str): Адрес клиента
        service_query (str): Название услуги
        limit (int): Максимум результатов
    
    Returns:
        list[dict]: Мастера с полной статистикой
    """
    # Геокодируем адрес клиента
    client_coords = await geocode_address(client_address)
    if not client_coords:
        raise ValueError(f"Не удалось определить координаты для адреса: {client_address}")
    
    client_lat, client_lon = client_coords
    
    conn = await get_db_connection()
    try:
        # Поиск мастеров с услугами и статистикой рейтинга
        query = """
            SELECT 
                u.telegram_id,
                u.first_name,
                u.last_name,
                u.user_code,
                u.average_rating,
                u.review_count,
                pa.address,
                pa.latitude,
                pa.longitude,
                ps.service_name,
                ps.description,
                ps.price_range,
                -- Клиентская база: уникальные клиенты
                (SELECT COUNT(DISTINCT client_telegram_id) 
                 FROM service_records 
                 WHERE provider_telegram_id = u.telegram_id 
                   AND status = 'completed') as client_base,
                -- Завершённые услуги
                (SELECT COUNT(*) 
                 FROM service_records 
                 WHERE provider_telegram_id = u.telegram_id 
                   AND status = 'completed') as completed_services
            FROM users u
            JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
            JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
            WHERE LOWER(ps.service_name) LIKE LOWER($1)
              AND pa.latitude IS NOT NULL 
              AND pa.longitude IS NOT NULL
            ORDER BY 
                -- Сначала по расстоянию, затем по рейтингу
                ( 6371 * acos(
                    cos(radians($2)) * cos(radians(pa.latitude)) * 
                    cos(radians(pa.longitude) - radians($3)) + 
                    sin(radians($2)) * sin(radians(pa.latitude))
                )) ASC,
                u.average_rating DESC NULLS LAST,
                u.review_count DESC
            LIMIT $4
        """
        
        # Выполняем поиск (с использованием триграмм для поиска по словам)
        rows = await conn.fetch(
            query,
            f"%{service_query}%",
            client_lat,
            client_lon,
            limit
        )
        
        if not rows:
            # Повторяем поиск с полнотекстовым поиском
            fuzzy_query = """
                SELECT 
                    u.telegram_id,
                    u.first_name,
                    u.last_name,
                    u.user_code,
                    u.average_rating,
                    u.review_count,
                    pa.address,
                    pa.latitude,
                    pa.longitude,
                    ps.service_name,
                    ps.description,
                    ps.price_range,
                    (SELECT COUNT(DISTINCT client_telegram_id) 
                     FROM service_records 
                     WHERE provider_telegram_id = u.telegram_id 
                       AND status = 'completed') as client_base,
                    (SELECT COUNT(*) 
                     FROM service_records 
                     WHERE provider_telegram_id = u.telegram_id 
                       AND status = 'completed') as completed_services
                FROM users u
                JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
                JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
                WHERE to_tsvector('russian', ps.service_name || ' ' || COALESCE(ps.description, ''))
                      @@ to_tsquery('russian', replace($1, ' ', ' & '))
                  AND pa.latitude IS NOT NULL 
                  AND pa.longitude IS NOT NULL
                ORDER BY 
                    ( 6371 * acos(
                        cos(radians($2)) * cos(radians(pa.latitude)) * 
                        cos(radians(pa.longitude) - radians($3)) + 
                        sin(radians($2)) * sin(radians(pa.latitude))
                    )) ASC,
                    u.average_rating DESC NULLS LAST,
                    u.review_count DESC
                LIMIT $4
            """
            
            rows = await conn.fetch(
                fuzzy_query,
                service_query,
                client_lat,
                client_lon,
                limit
            )
        
        # Формируем результат с расстоянием
        providers = []
        for row in rows:
            try:
                distance = calculate_distance(
                    client_lat,
                    client_lon,
                    float(row['latitude']),
                    float(row['longitude'])
                )
                
                full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
                
                providers.append({
                    'provider_id': row['telegram_id'],
                    'full_name': full_name,
                    'user_code': row['user_code'],
                    'address': row['address'],
                    'distance_km': round(distance, 1),
                    'service_name': row['service_name'],
                    'description': row['description'],
                    'price_range': row['price_range'],
                    'average_rating': float(row['average_rating']) if row['average_rating'] else 0.0,
                    'review_count': int(row['review_count']) if row['review_count'] else 0,
                    'client_base': int(row['client_base']) if row['client_base'] else 0,
                    'completed_services': int(row['completed_services']) if row['completed_services'] else 0
                })
            except (TypeError, ValueError):
                continue  # Пропускаем записи с некорректными координатами
        
        return providers[:limit]
    
    finally:
        await conn.close()

# ============================================================================
# РАСШИРЕННЫЙ ПОИСК МАСТЕРОВ С РЕЙТИНГОМ И СТАТИСТИКОЙ
# ============================================================================

async def search_nearby_providers_with_rating(client_address: str, service_query: str, limit: int = 10):
    """
    Расширенный поиск ближайших мастеров с рейтингом и статистикой
    
    Возвращает дополнительно:
    - Среднюю оценку мастера
    - Количество отзывов
    - Размер клиентской базы
    
    Args:
        client_address (str): Адрес клиента
        service_query (str): Название услуги
        limit (int): Максимум результатов
    
    Returns:
        list[dict]: Мастера с полной статистикой
    """
    # Геокодируем адрес клиента
    client_coords = await geocode_address(client_address)
    if not client_coords:
        raise ValueError(f"Не удалось определить координаты для адреса: {client_address}")
    
    client_lat, client_lon = client_coords
    
    conn = await get_db_connection()
    try:
        # Поиск мастеров с услугами и статистикой рейтинга (точное совпадение)
        exact_query = """
            SELECT 
                u.telegram_id,
                u.first_name,
                u.last_name,
                u.user_code,
                u.average_rating,
                u.review_count,
                pa.address,
                pa.latitude,
                pa.longitude,
                ps.service_name,
                ps.description,
                ps.price_range,
                -- Клиентская база: уникальные клиенты
                (SELECT COUNT(DISTINCT client_telegram_id) 
                 FROM service_records 
                 WHERE provider_telegram_id = u.telegram_id 
                   AND status = 'completed') as client_base,
                -- Завершённые услуги
                (SELECT COUNT(*) 
                 FROM service_records 
                 WHERE provider_telegram_id = u.telegram_id 
                   AND status = 'completed') as completed_services
            FROM users u
            JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
            JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
            WHERE LOWER(ps.service_name) = LOWER($1)
              AND pa.latitude IS NOT NULL 
              AND pa.longitude IS NOT NULL
            ORDER BY 
                ( 6371 * acos(
                    cos(radians($2)) * cos(radians(pa.latitude)) * 
                    cos(radians(pa.longitude) - radians($3)) + 
                    sin(radians($2)) * sin(radians(pa.latitude))
                )) ASC,
                u.average_rating DESC NULLS LAST,
                u.review_count DESC
            LIMIT $4
        """
        
        # Выполняем поиск точного совпадения
        rows = await conn.fetch(
            exact_query,
            service_query,
            client_lat,
            client_lon,
            limit
        )
        
        # Если нет точных совпадений — ищем по словам
        if not rows:
            fuzzy_query = """
                SELECT 
                    u.telegram_id,
                    u.first_name,
                    u.last_name,
                    u.user_code,
                    u.average_rating,
                    u.review_count,
                    pa.address,
                    pa.latitude,
                    pa.longitude,
                    ps.service_name,
                    ps.description,
                    ps.price_range,
                    (SELECT COUNT(DISTINCT client_telegram_id) 
                     FROM service_records 
                     WHERE provider_telegram_id = u.telegram_id 
                       AND status = 'completed') as client_base,
                    (SELECT COUNT(*) 
                     FROM service_records 
                     WHERE provider_telegram_id = u.telegram_id 
                       AND status = 'completed') as completed_services
                FROM users u
                JOIN provider_services ps ON u.telegram_id = ps.provider_telegram_id
                JOIN provider_addresses pa ON u.telegram_id = pa.provider_telegram_id
                WHERE to_tsvector('russian', ps.service_name || ' ' || COALESCE(ps.description, ''))
                      @@ plainto_tsquery('russian', $1)
                  AND pa.latitude IS NOT NULL 
                  AND pa.longitude IS NOT NULL
                ORDER BY 
                    ( 6371 * acos(
                        cos(radians($2)) * cos(radians(pa.latitude)) * 
                        cos(radians(pa.longitude) - radians($3)) + 
                        sin(radians($2)) * sin(radians(pa.latitude))
                    )) ASC,
                    u.average_rating DESC NULLS LAST,
                    u.review_count DESC
                LIMIT $4
            """
            
            rows = await conn.fetch(
                fuzzy_query,
                service_query,
                client_lat,
                client_lon,
                limit
            )
        
        # Формируем результат с расстоянием
        providers = []
        for row in rows:
            try:
                distance = calculate_distance(
                    client_lat,
                    client_lon,
                    float(row['latitude']),
                    float(row['longitude'])
                )
                
                full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
                
                providers.append({
                    'provider_id': row['telegram_id'],
                    'full_name': full_name,
                    'user_code': row['user_code'],
                    'address': row['address'],
                    'distance_km': round(distance, 1),
                    'service_name': row['service_name'],
                    'description': row['description'],
                    'price_range': row['price_range'],
                    'average_rating': float(row['average_rating']) if row['average_rating'] else 0.0,
                    'review_count': int(row['review_count']) if row['review_count'] else 0,
                    'client_base': int(row['client_base']) if row['client_base'] else 0,
                    'completed_services': int(row['completed_services']) if row['completed_services'] else 0
                })
            except (TypeError, ValueError):
                continue  # Пропускаем записи с некорректными координатами
        
        return providers[:limit]
    
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С ФОТОГРАФИЯМИ УСЛУГ
# ============================================================================

async def add_service_photo(record_id: int, photo_file_id: str, caption: str = None):
    """
    Добавляет фотографию к завершённой услуге
    
    Args:
        record_id (int): ID записи на услугу
        photo_file_id (str): file_id фотографии в Telegram
        caption (str, optional): Подпись к фотографии
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO service_photos (service_record_id, photo_file_id, caption)
            VALUES ($1, $2, $3)
            """,
            record_id, photo_file_id, caption
        )
    finally:
        await conn.close()


async def get_service_photos(record_id: int):
    """
    Получает все фотографии для записи на услугу
    
    Args:
        record_id (int): ID записи на услугу
    
    Returns:
        list[dict]: Список фотографий с метаданными
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT photo_file_id, caption, uploaded_at
            FROM service_photos
            WHERE service_record_id = $1
            ORDER BY uploaded_at ASC
            """,
            record_id
        )
        
        return [
            {
                'photo_file_id': row['photo_file_id'],
                'caption': row['caption'] or 'Результат работы',
                'uploaded_at': row['uploaded_at']
            }
            for row in rows
        ]
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С ОЖИДАЮЩИМИ ОЦЕНКАМИ
# ============================================================================

async def create_pending_review(client_id: int, provider_id: int, record_id: int, service_name: str):
    """
    Создаёт запись о ожидающей оценке для клиента
    
    Используется, когда клиент офлайн при завершении услуги.
    
    Args:
        client_id (int): ID клиента
        provider_id (int): ID мастера
        record_id (int): ID записи на услугу
        service_name (str): Название услуги
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO pending_reviews 
            (client_telegram_id, provider_telegram_id, service_record_id, service_name)
            VALUES ($1, $2, $3, $4)
            """,
            client_id, provider_id, record_id, service_name
        )
    finally:
        await conn.close()


async def get_pending_reviews(client_id: int):
    """
    Получает все ожидающие оценки клиента
    
    Args:
        client_id (int): ID клиента
    
    Returns:
        list[dict]: Список ожидающих оценок
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, provider_telegram_id, service_record_id, service_name, created_at
            FROM pending_reviews
            WHERE client_telegram_id = $1
            ORDER BY created_at ASC
            """,
            client_id
        )
        
        return [
            {
                'review_id': row['id'],
                'provider_id': row['provider_telegram_id'],
                'record_id': row['service_record_id'],
                'service_name': row['service_name'],
                'created_at': row['created_at']
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def delete_pending_review(review_id: int, client_id: int):
    """
    Удаляет запись об ожидающей оценке после её завершения
    
    Args:
        review_id (int): ID записи в pending_reviews
        client_id (int): ID клиента (для безопасности)
    """
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            DELETE FROM pending_reviews 
            WHERE id = $1 AND client_telegram_id = $2
            """,
            review_id, client_id
        )
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ ПРОСМОТРА ПРОФИЛЯ МАСТЕРА
# ============================================================================

async def get_provider_profile(provider_id: int):
    """
    Получает полную информацию о профиле мастера
    
    Args:
        provider_id (int): ID мастера (telegram_id)
    
    Returns:
        dict: Полная информация о мастере или None если не найден
    """
    conn = await get_db_connection()
    try:
        # Основная информация о мастере
        user_row = await conn.fetchrow(
            """
            SELECT 
                telegram_id,
                first_name,
                last_name,
                user_code,
                profile_photo_file_id,
                average_rating,
                review_count
            FROM users
            WHERE telegram_id = $1
            """,
            provider_id
        )
        
        if not user_row:
            return None
        
        # Адреса мастера
        addresses = await conn.fetch(
            """
            SELECT address, is_primary
            FROM provider_addresses
            WHERE provider_telegram_id = $1
            ORDER BY is_primary DESC, created_at ASC
            """,
            provider_id
        )
        
        # Услуги мастера
        services = await conn.fetch(
            """
            SELECT service_name, description, price_range
            FROM provider_services
            WHERE provider_telegram_id = $1
            ORDER BY created_at ASC
            """,
            provider_id
        )
        
        # Статистика (клиентская база, завершённые услуги)
        stats_row = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT client_telegram_id) as unique_clients,
                COUNT(*) as completed_services
            FROM service_records
            WHERE provider_telegram_id = $1 AND status = 'completed'
            """,
            provider_id
        )
        
        # Отзывы (последние 5)
        reviews = await conn.fetch(
            """
            SELECT 
                pr.rating,
                pr.comment,
                pr.created_at,
                u.first_name as client_first_name,
                u.last_name as client_last_name,
                u.user_code as client_code
            FROM provider_reviews pr
            JOIN users u ON pr.client_telegram_id = u.telegram_id
            WHERE pr.provider_telegram_id = $1
            ORDER BY pr.created_at DESC
            LIMIT 5
            """,
            provider_id
        )
        
        # Формируем полный профиль
        full_name = f"{user_row['first_name'] or ''} {user_row['last_name'] or ''}".strip() or "Мастер"
        
        return {
            'provider_id': user_row['telegram_id'],
            'full_name': full_name,
            'user_code': user_row['user_code'],
            'profile_photo_file_id': user_row['profile_photo_file_id'],
            'average_rating': float(user_row['average_rating']) if user_row['average_rating'] else 0.0,
            'review_count': int(user_row['review_count']) if user_row['review_count'] else 0,
            'addresses': [
                {
                    'address': addr['address'],
                    'is_primary': addr['is_primary']
                }
                for addr in addresses
            ],
            'services': [
                {
                    'service_name': srv['service_name'],
                    'description': srv['description'],
                    'price_range': srv['price_range']
                }
                for srv in services
            ],
            'client_base': int(stats_row['unique_clients']) if stats_row else 0,
            'completed_services': int(stats_row['completed_services']) if stats_row else 0,
            'reviews': [
                {
                    'rating': rev['rating'],
                    'comment': rev['comment'] or 'Без комментария',
                    'created_at': rev['created_at'],
                    'client_name': f"{rev['client_first_name'] or ''} {rev['client_last_name'] or ''}".strip() or "Клиент",
                    'client_code': rev['client_code']
                }
                for rev in reviews
            ]
        }
    
    finally:
        await conn.close()


async def get_client_provider_history(client_id: int):
    """
    Получает историю мастеров клиента для выбора профиля
    
    Возвращает уникальных мастеров с количеством записей и последней услугой.
    
    Args:
        client_id (int): ID клиента
    
    Returns:
        list[dict]: Список мастеров из истории
    """
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT 
                u.telegram_id as provider_id,
                u.first_name,
                u.last_name,
                u.user_code,
                u.average_rating,
                u.review_count,
                COUNT(sr.id) as total_records,
                MAX(sr.service_date) as last_service_date,
                STRING_AGG(DISTINCT sr.service_name, ', ') as services_list
            FROM service_records sr
            JOIN users u ON sr.provider_telegram_id = u.telegram_id
            WHERE sr.client_telegram_id = $1 
              AND sr.status IN ('completed', 'active')
            GROUP BY u.telegram_id, u.first_name, u.last_name, u.user_code, u.average_rating, u.review_count
            ORDER BY last_service_date DESC
            """,
            client_id
        )
        
        result = []
        for row in rows:
            full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "Мастер"
            result.append({
                'provider_id': row['provider_id'],
                'full_name': full_name,
                'user_code': row['user_code'],
                'average_rating': float(row['average_rating']) if row['average_rating'] else 0.0,
                'review_count': int(row['review_count']) if row['review_count'] else 0,
                'total_records': int(row['total_records']),
                'last_service_date': row['last_service_date'],
                'services_list': row['services_list']
            })
        
        return result
    
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С ОТЗЫВАМИ И РЕЙТИНГАМИ
# ============================================================================

async def create_provider_review(provider_id: int, client_id: int, service_record_id: int, rating: int, comment: str = None):
    """
    Создаёт отзыв о мастере после завершения услуги
    
    Автоматически обновляет кэшированные значения рейтинга в таблице users.
    
    Args:
        provider_id (int): ID мастера
        client_id (int): ID клиента
        service_record_id (int): ID записи на услугу
        rating (int): Оценка от 1 до 5
        comment (str, optional): Текстовый комментарий
    """
    conn = await get_db_connection()
    try:
        # Создаём отзыв
        await conn.execute(
            """
            INSERT INTO provider_reviews 
            (provider_telegram_id, client_telegram_id, service_record_id, rating, comment)
            VALUES ($1, $2, $3, $4, $5)
            """,
            provider_id, client_id, service_record_id, rating, comment
        )
        
        # Обновляем кэшированные значения рейтинга
        await conn.execute(
            """
            UPDATE users u
            SET 
                average_rating = (
                    SELECT AVG(rating) 
                    FROM provider_reviews 
                    WHERE provider_telegram_id = $1
                ),
                review_count = (
                    SELECT COUNT(*) 
                    FROM provider_reviews 
                    WHERE provider_telegram_id = $1
                )
            WHERE telegram_id = $1
            """,
            provider_id
        )
    finally:
        await conn.close()


async def get_provider_rating_summary(provider_id: int):
    """
    Получает сводку рейтинга мастера
    
    Возвращает среднюю оценку, количество отзывов и клиентскую базу.
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        dict: Сводка с полями:
            - average_rating: средняя оценка (0.0 если нет отзывов)
            - review_count: количество отзывов
            - client_base: количество уникальных клиентов
            - completed_services: количество завершённых услуг
    """
    conn = await get_db_connection()
    try:
        # Получаем кэшированные значения из таблицы users
        row = await conn.fetchrow(
            """
            SELECT average_rating, review_count
            FROM users
            WHERE telegram_id = $1
            """,
            provider_id
        )
        
        average_rating = float(row['average_rating']) if row and row['average_rating'] else 0.0
        review_count = int(row['review_count']) if row and row['review_count'] else 0
        
        # Получаем клиентскую базу (уникальные клиенты)
        client_base_row = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT client_telegram_id) as unique_clients,
                COUNT(*) as completed_services
            FROM service_records
            WHERE provider_telegram_id = $1 AND status = 'completed'
            """,
            provider_id
        )
        
        unique_clients = int(client_base_row['unique_clients']) if client_base_row else 0
        completed_services = int(client_base_row['completed_services']) if client_base_row else 0
        
        return {
            'average_rating': average_rating,
            'review_count': review_count,
            'client_base': unique_clients,
            'completed_services': completed_services
        }
    
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С ОТЗЫВАМИ И РЕЙТИНГАМИ
# ============================================================================

async def create_provider_review(provider_id: int, client_id: int, service_record_id: int, rating: int, comment: str = None):
    """
    Создаёт отзыв о мастере после завершения услуги
    
    Автоматически обновляет кэшированные значения рейтинга в таблице users.
    
    Args:
        provider_id (int): ID мастера
        client_id (int): ID клиента
        service_record_id (int): ID записи на услугу
        rating (int): Оценка от 1 до 5
        comment (str, optional): Текстовый комментарий
    """
    conn = await get_db_connection()
    try:
        # Создаём отзыв
        await conn.execute(
            """
            INSERT INTO provider_reviews 
            (provider_telegram_id, client_telegram_id, service_record_id, rating, comment)
            VALUES ($1, $2, $3, $4, $5)
            """,
            provider_id, client_id, service_record_id, rating, comment
        )
        
        # Обновляем кэшированные значения рейтинга
        await conn.execute(
            """
            UPDATE users u
            SET 
                average_rating = (
                    SELECT AVG(rating) 
                    FROM provider_reviews 
                    WHERE provider_telegram_id = $1
                ),
                review_count = (
                    SELECT COUNT(*) 
                    FROM provider_reviews 
                    WHERE provider_telegram_id = $1
                )
            WHERE telegram_id = $1
            """,
            provider_id
        )
    finally:
        await conn.close()


async def get_provider_rating_summary(provider_id: int):
    """
    Получает сводку рейтинга мастера
    
    Возвращает среднюю оценку, количество отзывов и клиентскую базу.
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        dict: Сводка с полями:
            - average_rating: средняя оценка (0.0 если нет отзывов)
            - review_count: количество отзывов
            - client_base: количество уникальных клиентов
            - completed_services: количество завершённых услуг
    """
    conn = await get_db_connection()
    try:
        # Получаем кэшированные значения из таблицы users
        row = await conn.fetchrow(
            """
            SELECT average_rating, review_count
            FROM users
            WHERE telegram_id = $1
            """,
            provider_id
        )
        
        average_rating = float(row['average_rating']) if row and row['average_rating'] else 0.0
        review_count = int(row['review_count']) if row and row['review_count'] else 0
        
        # Получаем клиентскую базу (уникальные клиенты)
        client_base_row = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT client_telegram_id) as unique_clients,
                COUNT(*) as completed_services
            FROM service_records
            WHERE provider_telegram_id = $1 AND status = 'completed'
            """,
            provider_id
        )
        
        unique_clients = int(client_base_row['unique_clients']) if client_base_row else 0
        completed_services = int(client_base_row['completed_services']) if client_base_row else 0
        
        return {
            'average_rating': average_rating,
            'review_count': review_count,
            'client_base': unique_clients,
            'completed_services': completed_services
        }
    
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ РАБОТЫ С НАЛОГОВЫМИ СТАВКАМИ
# ============================================================================

async def get_tax_rate(tax_type: str) -> float:
    """
    Получает налоговую ставку из БД
    
    Args:
        tax_type (str): Тип налога ('npd_individual', 'npd_entity', 'nds')
    
    Returns:
        float: Ставка в процентах или 4.0 (дефолт) если не найдена
    """
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT rate_percent FROM tax_rates WHERE tax_type = $1
            """,
            tax_type
        )
        return float(row['rate_percent']) if row else 4.0  # Дефолтная ставка НПД 4%
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ ИСТОРИИ ЗАПИСЕЙ (КЛИЕНТ И МАСТЕР)
# ============================================================================

async def get_client_history_for_month(client_id: int):
    """
    Получает историю записей клиента за последний месяц
    
    Возвращает сводку по мастерам: имя/фамилия, услуги, количество записей
    
    Args:
        client_id (int): ID клиента
    
    Returns:
        list[dict]: Список мастеров с услугами и количеством записей
    """
    conn = await get_db_connection()
    try:
        now = datetime.now().date()
        start_of_month = now.replace(day=1)
        
        # Получаем все записи клиента за месяц
        records = await conn.fetch(
            """
            SELECT 
                sr.provider_telegram_id,
                sr.service_name,
                u.first_name,
                u.last_name,
                u.user_code
            FROM service_records sr
            JOIN users u ON sr.provider_telegram_id = u.telegram_id
            WHERE sr.client_telegram_id = $1 
              AND sr.service_date >= $2
              AND sr.status IN ('active', 'completed')
            ORDER BY sr.service_date DESC, sr.service_time DESC
            """,
            client_id, start_of_month
        )
        
        # Группируем по мастерам
        providers_summary = {}
        for record in records:
            provider_id = record['provider_telegram_id']
            if provider_id not in providers_summary:
                providers_summary[provider_id] = {
                    'first_name': record['first_name'] or '',
                    'last_name': record['last_name'] or '',
                    'user_code': record['user_code'],
                    'services': {},
                    'total_records': 0
                }
            
            # Считаем услуги
            service_name = record['service_name']
            if service_name not in providers_summary[provider_id]['services']:
                providers_summary[provider_id]['services'][service_name] = 0
            providers_summary[provider_id]['services'][service_name] += 1
            providers_summary[provider_id]['total_records'] += 1
        
        # Преобразуем в список
        result = []
        for provider_id, data in providers_summary.items():
            full_name = f"{data['first_name']} {data['last_name']}".strip() or "Мастер"
            result.append({
                'provider_id': provider_id,
                'full_name': full_name,
                'user_code': data['user_code'],
                'services': data['services'],
                'total_records': data['total_records']
            })
        
        return sorted(result, key=lambda x: x['total_records'], reverse=True)
    
    finally:
        await conn.close()


async def get_provider_client_history_for_month(provider_id: int):
    """
    Получает историю клиентов мастера за последний месяц
    
    Возвращает сводку по клиентам: имя/фамилия, услуги, количество записей
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        list[dict]: Список клиентов с услугами и количеством записей
    """
    conn = await get_db_connection()
    try:
        now = datetime.now().date()
        start_of_month = now.replace(day=1)
        
        # Получаем все записи мастера за месяц
        records = await conn.fetch(
            """
            SELECT 
                sr.client_telegram_id,
                sr.service_name,
                u.first_name,
                u.last_name,
                u.user_code
            FROM service_records sr
            JOIN users u ON sr.client_telegram_id = u.telegram_id
            WHERE sr.provider_telegram_id = $1 
              AND sr.service_date >= $2
              AND sr.status IN ('active', 'completed')
            ORDER BY sr.service_date DESC, sr.service_time DESC
            """,
            provider_id, start_of_month
        )
        
        # Группируем по клиентам
        clients_summary = {}
        for record in records:
            client_id = record['client_telegram_id']
            if client_id not in clients_summary:
                clients_summary[client_id] = {
                    'first_name': record['first_name'] or '',
                    'last_name': record['last_name'] or '',
                    'user_code': record['user_code'],
                    'services': {},
                    'total_records': 0
                }
            
            # Считаем услуги
            service_name = record['service_name']
            if service_name not in clients_summary[client_id]['services']:
                clients_summary[client_id]['services'][service_name] = 0
            clients_summary[client_id]['services'][service_name] += 1
            clients_summary[client_id]['total_records'] += 1
        
        # Преобразуем в список
        result = []
        for client_id, data in clients_summary.items():
            full_name = f"{data['first_name']} {data['last_name']}".strip() or "Клиент"
            result.append({
                'client_id': client_id,
                'full_name': full_name,
                'user_code': data['user_code'],
                'services': data['services'],
                'total_records': data['total_records']
            })
        
        return sorted(result, key=lambda x: x['total_records'], reverse=True)
    
    finally:
        await conn.close()

# ============================================================================
# ФУНКЦИИ УЧЁТА ТРАТ МАСТЕРА
# ============================================================================

async def get_expenses_for_month(provider_id: int):
    """
    Получает все траты мастера за текущий месяц
    
    Args:
        provider_id (int): ID мастера
    
    Returns:
        list[dict]: Список трат с полями amount, description, created_at
    """
    conn = await get_db_connection()
    try:
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return await conn.fetch(
            """
            SELECT amount, description, created_at
            FROM expenses
            WHERE provider_telegram_id = $1 AND created_at >= $2
            ORDER BY created_at DESC
            """,
            provider_id, start_of_month
        )
    finally:
        await conn.close()