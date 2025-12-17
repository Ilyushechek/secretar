import asyncpg
import random
import string
from datetime import date, time, datetime, timedelta
from config import DATABASE_URL

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def is_user_registered(telegram_id: int) -> bool:
    conn = await get_db_connection()
    try:
        user = await conn.fetchrow("SELECT 1 FROM users WHERE telegram_id = $1", telegram_id)
        return user is not None
    finally:
        await conn.close()

async def get_password_hash(telegram_id: int):
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("SELECT password_hash FROM users WHERE telegram_id = $1", telegram_id)
        return row["password_hash"] if row else None
    finally:
        await conn.close()

async def create_user(telegram_id: int, password_hash: str):
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("""
            INSERT INTO users (telegram_id, password_hash)
            VALUES ($1, $2)
            RETURNING id
        """, telegram_id, password_hash)
        user_id = row["id"]
        user_code = f"{user_id:06d}"
        await conn.execute("UPDATE users SET user_code = $1 WHERE id = $2", user_code, user_id)
        return user_code
    finally:
        await conn.close()

async def update_password(telegram_id: int, password_hash: str):
    conn = await get_db_connection()
    try:
        await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE telegram_id = $2",
            password_hash, telegram_id
        )
    finally:
        await conn.close()

async def get_user_telegram_id_by_code(user_code: str):
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("SELECT telegram_id FROM users WHERE user_code = $1", user_code)
        return row["telegram_id"] if row else None
    finally:
        await conn.close()

async def create_chat(client_id: int, provider_id: int):
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("""
            INSERT INTO chats (client_telegram_id, provider_telegram_id, is_active)
            VALUES ($1, $2, true)
            RETURNING id
        """, client_id, provider_id)
        return row["id"]
    finally:
        await conn.close()

async def get_active_chat_by_client(client_id: int):
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("""
            SELECT * FROM chats 
            WHERE client_telegram_id = $1 AND is_active = true
        """, client_id)
        return row
    finally:
        await conn.close()

async def get_active_chat_by_provider(provider_id: int):
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("""
            SELECT * FROM chats 
            WHERE provider_telegram_id = $1 AND is_active = true
        """, provider_id)
        return row
    finally:
        await conn.close()

async def close_chat(chat_id: int):
    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE chats SET is_active = false WHERE id = $1", chat_id)
    finally:
        await conn.close()

# === НОВЫЕ ФУНКЦИИ ДЛЯ КАЛЕНДАРЯ ===

async def get_record_years(telegram_id: int, role: str) -> list[int]:
    conn = await get_db_connection()
    try:
        if role == "provider":
            query = "SELECT DISTINCT EXTRACT(YEAR FROM service_date) FROM service_records WHERE provider_telegram_id = $1"
        else:
            query = "SELECT DISTINCT EXTRACT(YEAR FROM service_date) FROM service_records WHERE client_telegram_id = $1"
        rows = await conn.fetch(query, telegram_id)
        return [int(row[0]) for row in rows if row[0] is not None]
    finally:
        await conn.close()

async def get_record_months(telegram_id: int, role: str, year: int) -> dict[int, int]:
    conn = await get_db_connection()
    try:
        if role == "provider":
            query = """
                SELECT EXTRACT(MONTH FROM service_date), COUNT(*)
                FROM service_records
                WHERE provider_telegram_id = $1 AND EXTRACT(YEAR FROM service_date) = $2
                GROUP BY EXTRACT(MONTH FROM service_date)
            """
        else:
            query = """
                SELECT EXTRACT(MONTH FROM service_date), COUNT(*)
                FROM service_records
                WHERE client_telegram_id = $1 AND EXTRACT(YEAR FROM service_date) = $2
                GROUP BY EXTRACT(MONTH FROM service_date)
            """
        rows = await conn.fetch(query, telegram_id, year)
        return {int(row[0]): row[1] for row in rows if row[0] is not None}
    finally:
        await conn.close()

async def get_record_days(telegram_id: int, role: str, year: int, month: int) -> dict[int, int]:
    conn = await get_db_connection()
    try:
        if role == "provider":
            query = """
                SELECT EXTRACT(DAY FROM service_date), COUNT(*)
                FROM service_records
                WHERE provider_telegram_id = $1 
                AND EXTRACT(YEAR FROM service_date) = $2
                AND EXTRACT(MONTH FROM service_date) = $3
                GROUP BY EXTRACT(DAY FROM service_date)
            """
        else:
            query = """
                SELECT EXTRACT(DAY FROM service_date), COUNT(*)
                FROM service_records
                WHERE client_telegram_id = $1 
                AND EXTRACT(YEAR FROM service_date) = $2
                AND EXTRACT(MONTH FROM service_date) = $3
                GROUP BY EXTRACT(DAY FROM service_date)
            """
        rows = await conn.fetch(query, telegram_id, year, month)
        return {int(row[0]): row[1] for row in rows if row[0] is not None}
    finally:
        await conn.close()

async def get_records_by_date(telegram_id: int, role: str, year: int, month: int, day: int):
    conn = await get_db_connection()
    try:
        target_date = date(year, month, day)
        if role == "provider":
            query = """
                SELECT * FROM service_records
                WHERE provider_telegram_id = $1 AND service_date = $2
                ORDER BY service_time
            """
        else:
            query = """
                SELECT * FROM service_records
                WHERE client_telegram_id = $1 AND service_date = $2
                ORDER BY service_time
            """
        return await conn.fetch(query, telegram_id, target_date)
    finally:
        await conn.close()

# === ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ ЗАПИСИ (обновлена) ===

# === ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ ЗАПИСИ (обновлена сигнатура) ===

async def create_service_record(
    provider_id: int,
    client_id: int,
    service_name: str,
    cost: int,
    address: str,
    date: date,      # ← тип: datetime.date
    time: time,      # ← тип: datetime.time
    comments: str
):
    conn = await get_db_connection()
    try:
        await conn.execute("""
            INSERT INTO service_records (
                provider_telegram_id, client_telegram_id, service_name,
                cost, address, service_date, service_time, comments
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, provider_id, client_id, service_name, cost, address, date, time, comments)
    finally:
        await conn.close()

async def get_records_by_date_for_provider(provider_id: int, year: int, month: int, day: int):
    """Получает записи провайдера на конкретную дату (для отображения при создании новой записи)"""
    conn = await get_db_connection()
    try:
        target_date = date(year, month, day)
        query = """
            SELECT service_time, service_name
            FROM service_records
            WHERE provider_telegram_id = $1 AND service_date = $2
            ORDER BY service_time
        """
        return await conn.fetch(query, provider_id, target_date)
    finally:
        await conn.close()

# database.py — добавьте в конец файла

async def get_records_for_24h_reminder():
    """Получает записи, для которых нужно отправить напоминание за 24 часа"""
    conn = await get_db_connection()
    try:
        query = """
            SELECT 
                id, provider_telegram_id, client_telegram_id,
                service_name, cost, address, service_date, service_time, comments
            FROM service_records
            WHERE 
                sent_24h_reminder = false
                AND service_date + service_time >= NOW()
                AND service_date + service_time <= NOW() + INTERVAL '24 hours'
        """
        return await conn.fetch(query)
    finally:
        await conn.close()

async def get_records_for_1h_reminder():
    """Получает записи, для которых нужно отправить напоминание за 1 час"""
    conn = await get_db_connection()
    try:
        query = """
            SELECT 
                id, provider_telegram_id, client_telegram_id,
                service_name, cost, address, service_date, service_time, comments
            FROM service_records
            WHERE 
                sent_1h_reminder = false
                AND service_date + service_time >= NOW()
                AND service_date + service_time <= NOW() + INTERVAL '1 hour'
        """
        return await conn.fetch(query)
    finally:
        await conn.close()

async def mark_24h_reminder_sent(record_id: int):
    """Отмечает, что напоминание за 24ч отправлено"""
    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE service_records SET sent_24h_reminder = true WHERE id = $1", record_id)
    finally:
        await conn.close()

async def mark_1h_reminder_sent(record_id: int):
    """Отмечает, что напоминание за 1ч отправлено"""
    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE service_records SET sent_1h_reminder = true WHERE id = $1", record_id)
    finally:
        await conn.close()

# database.py

async def create_notification(telegram_id: int, role: str, message_text: str):
    """Создаёт уведомление для пользователя определённой роли"""
    conn = await get_db_connection()
    try:
        await conn.execute("""
            INSERT INTO notifications (user_telegram_id, role, message_text)
            VALUES ($1, $2, $3)
        """, telegram_id, role, message_text)
    finally:
        await conn.close()

async def get_unread_count(telegram_id: int, role: str) -> int:
    """Получает количество непрочитанных уведомлений для пользователя и роли"""
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("""
            SELECT COUNT(*) FROM notifications
            WHERE user_telegram_id = $1 AND role = $2 AND is_read = false
        """, telegram_id, role)
        return row[0] if row else 0
    finally:
        await conn.close()

async def mark_notifications_as_read(telegram_id: int, role: str):
    """Помечает все уведомления как прочитанные"""
    conn = await get_db_connection()
    try:
        await conn.execute("""
            UPDATE notifications
            SET is_read = true
            WHERE user_telegram_id = $1 AND role = $2 AND is_read = false
        """, telegram_id, role)
    finally:
        await conn.close()

async def get_unread_notifications(telegram_id: int, role: str):
    """Получает список непрочитанных уведомлений"""
    conn = await get_db_connection()
    try:
        return await conn.fetch("""
            SELECT message_text, created_at
            FROM notifications
            WHERE user_telegram_id = $1 AND role = $2 AND is_read = false
            ORDER BY created_at
        """, telegram_id, role)
    finally:
        await conn.close()

async def update_user_email(telegram_id: int, email: str):
    """Обновляет email пользователя"""
    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE users SET email = $1 WHERE telegram_id = $2", email, telegram_id)
    finally:
        await conn.close()

async def get_user_email(telegram_id: int):
    """Получает email пользователя"""
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("SELECT email FROM users WHERE telegram_id = $1", telegram_id)
        return row["email"] if row else None
    finally:
        await conn.close()

async def generate_reset_code(telegram_id: int):
    """Генерирует и сохраняет код сброса пароля"""
    code = ''.join(random.choices(string.digits, k=6))
    expires = datetime.utcnow() + timedelta(minutes=10)
    conn = await get_db_connection()
    try:
        await conn.execute("""
            UPDATE users 
            SET reset_code = $1, reset_code_expires = $2 
            WHERE telegram_id = $3
        """, code, expires, telegram_id)
        return code
    finally:
        await conn.close()

async def verify_reset_code(telegram_id: int, code: str) -> bool:
    """Проверяет код сброса пароля"""
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow("""
            SELECT reset_code, reset_code_expires 
            FROM users 
            WHERE telegram_id = $1
        """, telegram_id)
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
    """Очищает код после успешного сброса"""
    conn = await get_db_connection()
    try:
        await conn.execute("""
            UPDATE users 
            SET reset_code = NULL, reset_code_expires = NULL 
            WHERE telegram_id = $1
        """, telegram_id)
    finally:
        await conn.close()