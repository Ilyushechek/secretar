"""
main.py
=======
Точка входа в приложение Telegram-бота Secretariat
Запускает бота, планировщик задач и обработчики
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import BOT_TOKEN

# Настройка логгера для записи всех событий
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаём экземпляр бота с токеном из конфигурации
bot = Bot(token=BOT_TOKEN)

# Создаём диспетчер для обработки сообщений
dp = Dispatcher(storage=MemoryStorage())

# Создаём планировщик задач для периодических операций
scheduler = AsyncIOScheduler()


# ============================================================================
# ФУНКЦИИ НАПОМИНАНИЙ (24 часа и 1 час до записи)
# ============================================================================

async def send_24h_reminders():
    """
    Отправляет напоминания за 24 часа до записи
    
    Выполняется каждые 10 минут
    """
    from database import (
        get_records_for_24h_reminder, 
        mark_24h_reminder_sent
    )
    
    try:
        # Получаем записи, для которых нужно отправить напоминание
        records = await get_records_for_24h_reminder()
        
        # Обрабатываем каждую запись
        for record in records:
            try:
                # Формируем сообщение для мастера
                master_text = (
                    f"🔔 <b>Напоминание (за 24 часа)</b>\n\n"
                    f"У вас запись на услугу:\n"
                    f"🔹 {record['service_name']}\n"
                    f"🔹 Дата: {record['service_date']}\n"
                    f"🔹 Время: {record['service_time']}\n"
                    f"🔹 Адрес: {record['address']}\n"
                    f"🔹 Клиент ID: {record['client_telegram_id']}"
                )
                # Отправляем мастеру
                await bot.send_message(
                    record["provider_telegram_id"], 
                    master_text, 
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки мастеру: {e}")
            
            try:
                # Формируем сообщение для клиента
                client_text = (
                    f"🔔 <b>Напоминание (за 24 часа)</b>\n\n"
                    f"У вас запись на услугу:\n"
                    f"🔹 {record['service_name']}\n"
                    f"🔹 Дата: {record['service_date']}\n"
                    f"🔹 Время: {record['service_time']}\n"
                    f"🔹 Адрес: {record['address']}"
                )
                # Отправляем клиенту
                await bot.send_message(
                    record["client_telegram_id"], 
                    client_text, 
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту: {e}")
            
            # Помечаем напоминание как отправленное
            await mark_24h_reminder_sent(record["id"])
    
    except Exception as e:
        logger.error(f"Ошибка в задаче 24h напоминаний: {e}")


async def send_1h_reminders():
    """
    Отправляет напоминания за 1 час до записи
    
    Выполняется каждые 5 минут
    """
    from database import (
        get_records_for_1h_reminder, 
        mark_1h_reminder_sent
    )
    
    try:
        # Получаем записи, для которых нужно отправить напоминание
        records = await get_records_for_1h_reminder()
        
        # Обрабатываем каждую запись
        for record in records:
            try:
                # Формируем сообщение для мастера
                master_text = (
                    f"⏰ <b>Напоминание (за 1 час)</b>\n\n"
                    f"У вас запись на услугу:\n"
                    f"🔹 {record['service_name']}\n"
                    f"🔹 Дата: {record['service_date']}\n"
                    f"🔹 Время: {record['service_time']}\n"
                    f"🔹 Адрес: {record['address']}\n"
                    f"🔹 Клиент ID: {record['client_telegram_id']}"
                )
                # Отправляем мастеру
                await bot.send_message(
                    record["provider_telegram_id"], 
                    master_text, 
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки мастеру: {e}")
            
            try:
                # Формируем сообщение для клиента
                client_text = (
                    f"⏰ <b>Напоминание (за 1 час)</b>\n\n"
                    f"У вас запись на услугу:\n"
                    f"🔹 {record['service_name']}\n"
                    f"🔹 Дата: {record['service_date']}\n"
                    f"🔹 Время: {record['service_time']}\n"
                    f"🔹 Адрес: {record['address']}"
                )
                # Отправляем клиенту
                await bot.send_message(
                    record["client_telegram_id"], 
                    client_text, 
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту: {e}")
            
            # Помечаем напоминание как отправленное
            await mark_1h_reminder_sent(record["id"])
    
    except Exception as e:
        logger.error(f"Ошибка в задаче 1h напоминаний: {e}")


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================================================

async def main():
    """
    Основная функция запуска бота
    
    Инициализирует планировщик и подключает обработчики
    """
    # ============================================================================
    # НАСТРОЙКА ПЛАНИРОВЩИКА ЗАДАЧ
    # ============================================================================
    
    # Добавляем задачу напоминаний за 24 часа (каждые 10 минут)
    scheduler.add_job(
        send_24h_reminders,
        trigger=IntervalTrigger(minutes=10),
        id='24h_reminders',
        replace_existing=True  # Заменять существующую задачу при повторном запуске
    )
    
    # Добавляем задачу напоминаний за 1 час (каждые 5 минут)
    scheduler.add_job(
        send_1h_reminders,
        trigger=IntervalTrigger(minutes=5),
        id='1h_reminders',
        replace_existing=True
    )
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("Планировщик запущен")
    
    # ============================================================================
    # ПОДКЛЮЧЕНИЕ ОБРАБОТЧИКОВ (ВАЖЕН ПОРЯДОК!)
    # ============================================================================
    
    # Импортируем роутеры НАПРЯМУЮ (без использования handlers/__init__.py)
    from handlers.logout import router as logout_router
    from handlers.start import router as start_router
    from handlers.registration import router as registration_router
    from handlers.login import router as login_router
    from handlers.password_reset import router as password_reset_router
    from handlers.chat import router as chat_router
    from handlers.service_record import router as service_record_router
    from handlers.completion import router as completion_router
    from handlers.cancellation import router as cancellation_router
    from handlers.expenses import router as expenses_router
    from handlers.statistics import router as statistics_router
    from handlers.client_history import router as client_history_router
    from handlers.provider_history import router as provider_history_router
    from handlers.provider_expenses_view import router as provider_expenses_router
    from handlers.repeat_requests import router as repeat_requests_router
    from handlers.provider_requests import router as provider_requests_router
    from handlers.nearby_search import router as nearby_search_router
    from handlers.reviews import router as reviews_router
    
    # Обработчики подключаются в порядке приоритета:
    # 1. logout - самый первый (без зависимостей от других обработчиков)
    # 2. start - команда /start
    # 3. registration - регистрация
    # 4. ... остальные в произвольном порядке
    
    dp.include_router(logout_router)        # ← самый первый (без зависимостей)
    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(login_router)
    dp.include_router(password_reset_router)
    dp.include_router(chat_router)
    dp.include_router(service_record_router)
    dp.include_router(completion_router)
    dp.include_router(cancellation_router)
    dp.include_router(expenses_router)
    dp.include_router(statistics_router)
    dp.include_router(client_history_router)
    dp.include_router(provider_history_router)
    dp.include_router(provider_expenses_router)
    dp.include_router(repeat_requests_router)
    dp.include_router(provider_requests_router)
    dp.include_router(nearby_search_router)
    dp.include_router(reviews_router)
    
    logger.info("Все обработчики подключены")
    
    # ============================================================================
    # ЗАПУСК БОТА
    # ============================================================================
    
    logger.info("Бот запускается...")
    
    # Запускаем бота в режиме опроса (polling)
    await dp.start_polling(bot)


# ============================================================================
# ТОЧКА ВХОДА В ПРИЛОЖЕНИЕ
# ============================================================================

if __name__ == "__main__":
    """
    Проверка, что файл запущен напрямую (а не импортирован)
    """
    # Запускаем основную функцию
    asyncio.run(main())