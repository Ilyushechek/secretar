# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import BOT_TOKEN
from handlers import logout, calendar, service_record, chat, password_reset, login, registration, start
from database import get_records_for_24h_reminder, get_records_for_1h_reminder, mark_24h_reminder_sent, mark_1h_reminder_sent

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключаем роутеры
dp.include_router(logout.router)
dp.include_router(calendar.router)
dp.include_router(service_record.router)
dp.include_router(chat.router)
dp.include_router(password_reset.router)
dp.include_router(login.router)
dp.include_router(registration.router)
dp.include_router(start.router)

# === ФУНКЦИИ НАПОМИНАНИЙ ===

async def send_24h_reminders():
    records = await get_records_for_24h_reminder()
    for record in records:
        try:
            # Для мастера
            master_text = (
                f"🔔 <b>Напоминание (за 24 часа)</b>\n\n"
                f"У вас запись на услугу:\n"
                f"🔹 {record['service_name']}\n"
                f"🔹 Дата: {record['service_date']}\n"
                f"🔹 Время: {record['service_time']}\n"
                f"🔹 Адрес: {record['address']}\n"
                f"🔹 Клиент ID: {record['client_telegram_id']}"
            )
            await bot.send_message(record["provider_telegram_id"], master_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось отправить напоминание мастеру {record['provider_telegram_id']}: {e}")
        
        try:
            # Для клиента
            client_text = (
                f"🔔 <b>Напоминание (за 24 часа)</b>\n\n"
                f"У вас запись на услугу:\n"
                f"🔹 {record['service_name']}\n"
                f"🔹 Дата: {record['service_date']}\n"
                f"🔹 Время: {record['service_time']}\n"
                f"🔹 Адрес: {record['address']}"
            )
            await bot.send_message(record["client_telegram_id"], client_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось отправить напоминание клиенту {record['client_telegram_id']}: {e}")
        
        await mark_24h_reminder_sent(record["id"])

async def send_1h_reminders():
    records = await get_records_for_1h_reminder()
    for record in records:
        try:
            # Для мастера
            master_text = (
                f"⏰ <b>Напоминание (за 1 час)</b>\n\n"
                f"У вас запись на услугу:\n"
                f"🔹 {record['service_name']}\n"
                f"🔹 Дата: {record['service_date']}\n"
                f"🔹 Время: {record['service_time']}\n"
                f"🔹 Адрес: {record['address']}\n"
                f"🔹 Клиент ID: {record['client_telegram_id']}"
            )
            await bot.send_message(record["provider_telegram_id"], master_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось отправить напоминание мастеру {record['provider_telegram_id']}: {e}")
        
        try:
            # Для клиента
            client_text = (
                f"⏰ <b>Напоминание (за 1 час)</b>\n\n"
                f"У вас запись на услугу:\n"
                f"🔹 {record['service_name']}\n"
                f"🔹 Дата: {record['service_date']}\n"
                f"🔹 Время: {record['service_time']}\n"
                f"🔹 Адрес: {record['address']}"
            )
            await bot.send_message(record["client_telegram_id"], client_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось отправить напоминание клиенту {record['client_telegram_id']}: {e}")
        
        await mark_1h_reminder_sent(record["id"])

async def main():
    # Запускаем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_24h_reminders, IntervalTrigger(minutes=10))  # Проверка каждые 10 минут
    scheduler.add_job(send_1h_reminders, IntervalTrigger(minutes=5))    # Проверка каждые 5 минут
    scheduler.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

