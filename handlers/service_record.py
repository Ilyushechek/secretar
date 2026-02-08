"""
handlers/service_record.py
==========================
Обработчик создания записей на услуги
Поддерживает ввод всех параметров услуги и сохранение в БД
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
import logging
from datetime import datetime
from FSMstates import ServiceRecordStates
from database import (
    get_user_telegram_id_by_code,
    get_active_chat_by_provider,
    create_service_record,
    get_records_by_date_for_provider,
    create_notification,
    get_user_name
)
from keyboards import (
    provider_menu_keyboard, 
    client_menu_keyboard, 
    cancel_menu_keyboard
)
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки записей
router = Router()


@router.message(F.text == "Добавить запись")
async def start_service_record_from_menu(message: Message, state: FSMContext):
    """
    Начало создания записи на услугу
    
    Проверяет наличие активного чата для автоматического определения клиента
    Или запрашивает ID клиента вручную
    
    Args:
        message (Message): Входящее сообщение
        state (FSMContext): Контекст состояния
    """
    # Получаем сохранённые данные из состояния
    data = await state.get_data()
    
    # Если клиент уже задан (например, после чата) - пропускаем ввод ID
    if data.get("client_telegram_id"):
        await message.answer("Введите название услуги:")
        await state.set_state(ServiceRecordStates.waiting_for_service_name)
        return
    
    # Очищаем старые данные записи
    await state.update_data(client_telegram_id=None, from_chat=False)
    
    # Проверяем наличие активного чата
    active_chat = await get_active_chat_by_provider(message.from_user.id)
    if active_chat and active_chat["is_active"]:
        # Если есть активный чат - используем клиента из него
        client_id = active_chat["client_telegram_id"]
        await state.update_data(client_telegram_id=client_id, from_chat=True)
        await message.answer("Введите название услуги:")
        await state.set_state(ServiceRecordStates.waiting_for_service_name)
    else:
        # Нет активного чата - запрашиваем ID клиента вручную
        await message.answer(
            "Введите 6-значный ID клиента:", 
            reply_markup=cancel_menu_keyboard()
        )
        await state.set_state(ServiceRecordStates.waiting_for_client_id)


@router.message(ServiceRecordStates.waiting_for_client_id)
async def process_client_id(message: Message, state: FSMContext):
    """
    Обработка ввода ID клиента
    
    Проверяет формат и существование клиента
    
    Args:
        message (Message): Сообщение с ID клиента
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Проверяем формат ID (6 цифр)
    user_code = message.text.strip()
    if not user_code.isdigit() or len(user_code) != 6:
        await message.answer(
            "Неверный формат ID. Введите 6 цифр:", 
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Получаем telegram_id клиента по коду
    client_telegram_id = await get_user_telegram_id_by_code(user_code)
    if not client_telegram_id:
        await message.answer(
            "Клиент с таким ID не найден. Попробуйте снова:", 
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Сохраняем ID клиента в состоянии
    await state.update_data(
        client_telegram_id=client_telegram_id, 
        from_chat=False
    )
    
    # Запрашиваем название услуги
    await message.answer("Введите название услуги:")
    await state.set_state(ServiceRecordStates.waiting_for_service_name)


@router.message(ServiceRecordStates.waiting_for_service_name)
async def process_service_name(message: Message, state: FSMContext):
    """
    Обработка названия услуги
    
    Args:
        message (Message): Сообщение с названием
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Сохраняем название и запрашиваем стоимость
    await state.update_data(service_name=message.text)
    await message.answer("Введите стоимость услуги (в рублях):")
    await state.set_state(ServiceRecordStates.waiting_for_cost)


@router.message(ServiceRecordStates.waiting_for_cost)
async def process_cost(message: Message, state: FSMContext):
    """
    Обработка стоимости услуги
    
    Проверяет, что введено число
    
    Args:
        message (Message): Сообщение со стоимостью
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Проверяем, что введено число
    if not message.text.isdigit():
        await message.answer("Введите число (без букв и символов):")
        return
    
    # Сохраняем стоимость и запрашиваем адрес
    await state.update_data(cost=message.text)
    await message.answer("Введите адрес проведения услуги:")
    await state.set_state(ServiceRecordStates.waiting_for_address)


@router.message(ServiceRecordStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """
    Обработка адреса проведения услуги
    
    Args:
        message (Message): Сообщение с адресом
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Сохраняем адрес и запрашиваем дату
    await state.update_data(address=message.text)
    await message.answer("Введите дату (например, 15.12.2025):")
    await state.set_state(ServiceRecordStates.waiting_for_date)


@router.message(ServiceRecordStates.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """
    Обработка даты услуги
    
    Поддерживает форматы: ДД.ММ.ГГГГ и ГГГГ-ММ-ДД
    После ввода даты показывает существующие записи на эту дату
    
    Args:
        message (Message): Сообщение с датой
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Пробуем распарсить дату в разных форматах
    input_date = message.text.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            date_obj = datetime.strptime(input_date, fmt).date()
            # Сохраняем дату в состоянии
            await state.update_data(date=date_obj)
            
            # Получаем существующие записи на эту дату
            provider_id = message.from_user.id
            records = await get_records_by_date_for_provider(
                provider_id, 
                date_obj.year, 
                date_obj.month, 
                date_obj.day
            )
            
            # Формируем сообщение со списком записей
            if records:
                response = "На эту дату уже есть записи:\n"
                for record in records:
                    response += (
                        f"• {record['service_time'].strftime('%H:%M')} — "
                        f"{record['service_name']}\n"
                    )
                response += "\nВведите время (например, 14:30):"
                await message.answer(response)
            else:
                await message.answer(
                    "На эту дату нет записей.\nВведите время (например, 14:30):"
                )
            
            # Переходим к вводу времени
            await state.set_state(ServiceRecordStates.waiting_for_time)
            return
        except ValueError:
            continue
    
    # Если ни один формат не подошёл - просим ввести снова
    await message.answer(
        "Неверный формат даты. Используйте ДД.ММ.ГГГГ или ГГГГ-ММ-ДД:"
    )


@router.message(ServiceRecordStates.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    """
    Обработка времени услуги
    
    Поддерживает формат ЧЧ:ММ
    
    Args:
        message (Message): Сообщение со временем
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Пробуем распарсить время
    try:
        time_obj = datetime.strptime(message.text.strip(), "%H:%M").time()
        # Сохраняем время и запрашиваем комментарии
        await state.update_data(time=time_obj)
        await message.answer("Введите комментарии (или '-' если нет):")
        await state.set_state(ServiceRecordStates.waiting_for_comments)
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ:")


@router.message(ServiceRecordStates.waiting_for_comments)
async def process_comments_and_send(message: Message, state: FSMContext, bot):
    """
    Обработка комментариев и сохранение записи в БД
    
    Создаёт запись, сохраняет уведомления для обеих сторон
    
    Args:
        message (Message): Сообщение с комментариями
        state (FSMContext): Контекст состояния
        bot (Bot): Экземпляр бота
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Обрабатываем комментарии
    comments = message.text if message.text != "-" else "Комментариев нет"
    
    # Получаем все данные из состояния
    data = await state.get_data()
    client_id = data["client_telegram_id"]
    service_name = data["service_name"]
    cost = data["cost"]
    address = data["address"]
    date_obj = data["date"]
    time_obj = data["time"]
    
    # Сохраняем запись в БД
    await create_service_record(
        provider_id=message.from_user.id,
        client_id=client_id,
        service_name=service_name,
        cost=int(cost),
        address=address,
        date=date_obj,
        time=time_obj,
        comments=comments
    )
    
    # Получаем имя и фамилию клиента из БД для отображения
    client_info = await get_user_name(client_id)
    if client_info and (client_info["first_name"] or client_info["last_name"]):
        name_parts = []
        if client_info["first_name"]:
            name_parts.append(client_info["first_name"])
        if client_info["last_name"]:
            name_parts.append(client_info["last_name"])
        client_name = " ".join(name_parts)
    else:
        client_name = "Клиент"
    client_code = client_info["user_code"] if client_info else "???"
    
    # Формируем текст записи для уведомления
    record_text = (
        f"📄 <b>Новая запись на услугу</b>\n\n"
        f"🔹 Услуга: {service_name}\n"
        f"🔹 Стоимость: {cost} руб.\n"
        f"🔹 Клиент: {client_name} (ID: {client_code})\n"
        f"🔹 Адрес: {address}\n"
        f"🔹 Дата: {date_obj.strftime('%d.%m.%Y')}\n"
        f"🔹 Время: {time_obj.strftime('%H:%M')}\n"
        f"🔹 Комментарии: {comments}"
    )
    
    # Ограничиваем длину сообщения для Telegram (макс. 4096 символов)
    if len(record_text) > 4000:
        record_text = record_text[:3997] + "..."
    
    # ============================================================================
    # СОХРАНЯЕМ УВЕДОМЛЕНИЯ ДЛЯ ОБЕИХ СТОРОН (БЕЗ ПРЯМОЙ ОТПРАВКИ)
    # ============================================================================
    
    # Для мастера - сохраняем уведомление
    await create_notification(
        telegram_id=message.from_user.id,
        role="provider",
        message_text=record_text
    )
    
    # Для клиента - сохраняем уведомление (если не сам себе)
    if client_id != message.from_user.id:
        await create_notification(
            telegram_id=client_id,
            role="client",
            message_text=record_text
        )
    
    # ============================================================================
    # ПОДТВЕРЖДЕНИЕ МАСТЕРУ
    # ============================================================================
    
    if client_id != message.from_user.id:
        await message.answer(
            "✅ Запись сохранена. Клиент получит уведомление при входе как клиент."
        )
    else:
        await message.answer("✅ Запись сохранена.")
    
    # ============================================================================
    # ВОЗВРАТ В МЕНЮ
    # ============================================================================
    
    # Сохраняем роль при очистке состояния
    current_data = await state.get_data()
    role = current_data.get("user_role", "client")
    await state.clear()
    await state.update_data(user_role=role)
    
    # Показываем соответствующее меню
    menu_kb = provider_menu_keyboard if role == "provider" else client_menu_keyboard
    await message.answer("Вы вернулись в меню.", reply_markup=menu_kb())