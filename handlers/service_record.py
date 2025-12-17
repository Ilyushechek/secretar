# handlers/service_record.py


from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
from datetime import datetime
from FSMstates import ServiceRecordStates
from database import (
    get_user_telegram_id_by_code,
    get_active_chat_by_provider,
    create_service_record,
    get_records_by_date_for_provider,
    create_notification  # ← ДОБАВЬТЕ ЭТУ СТРОКУ!
)
from keyboards import provider_menu_keyboard, client_menu_keyboard, cancel_menu_keyboard
import logging

router = Router()

@router.message(F.text == "Добавить запись")
async def start_service_record_from_menu(message: Message, state: FSMContext):
    await state.update_data(client_telegram_id=None, from_chat=False)
    
    active_chat = await get_active_chat_by_provider(message.from_user.id)
    if active_chat and active_chat["is_active"]:
        client_id = active_chat["client_telegram_id"]
        await state.update_data(client_telegram_id=client_id, from_chat=True)
        await message.answer("Введите название услуги:")
        await state.set_state(ServiceRecordStates.waiting_for_service_name)
    else:
        await message.answer("Введите 6-значный ID клиента:", reply_markup=cancel_menu_keyboard())
        await state.set_state(ServiceRecordStates.waiting_for_client_id)

@router.message(ServiceRecordStates.waiting_for_client_id)
async def process_client_id(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    user_code = message.text.strip()
    if not user_code.isdigit() or len(user_code) != 6:
        await message.answer("Неверный формат ID. Введите 6 цифр:", reply_markup=cancel_menu_keyboard())
        return
    client_telegram_id = await get_user_telegram_id_by_code(user_code)
    if not client_telegram_id:
        await message.answer("Клиент с таким ID не найден. Попробуйте снова:", reply_markup=cancel_menu_keyboard())
        return
    await state.update_data(client_telegram_id=client_telegram_id, from_chat=False)
    await message.answer("Введите название услуги:")
    await state.set_state(ServiceRecordStates.waiting_for_service_name)

@router.message(ServiceRecordStates.waiting_for_service_name)
async def process_service_name(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    await state.update_data(service_name=message.text)
    await message.answer("Введите стоимость услуги (в рублях):")
    await state.set_state(ServiceRecordStates.waiting_for_cost)

@router.message(ServiceRecordStates.waiting_for_cost)
async def process_cost(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    if not message.text.isdigit():
        await message.answer("Введите число (без букв и символов):")
        return
    await state.update_data(cost=message.text)
    await message.answer("Введите адрес проведения услуги:")
    await state.set_state(ServiceRecordStates.waiting_for_address)

@router.message(ServiceRecordStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    await state.update_data(address=message.text)
    await message.answer("Введите дату (например, 15.12.2025):")
    await state.set_state(ServiceRecordStates.waiting_for_date)

@router.message(ServiceRecordStates.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    input_date = message.text.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            date_obj = datetime.strptime(input_date, fmt).date()
            await state.update_data(date=date_obj)
            
            # Показываем существующие записи на эту дату
            provider_id = message.from_user.id
            records = await get_records_by_date_for_provider(
                provider_id, 
                date_obj.year, 
                date_obj.month, 
                date_obj.day
            )
            
            if records:
                response = "На эту дату уже есть записи:\n"
                for record in records:
                    response += f"• {record['service_time'].strftime('%H:%M')} — {record['service_name']}\n"
                response += "\nВведите время (например, 14:30):"
                await message.answer(response)
            else:
                await message.answer("На эту дату нет записей.\nВведите время (например, 14:30):")
            
            await state.set_state(ServiceRecordStates.waiting_for_time)
            return
        except ValueError:
            continue
    await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ или ГГГГ-ММ-ДД:")

@router.message(ServiceRecordStates.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    try:
        time_obj = datetime.strptime(message.text.strip(), "%H:%M").time()
        await state.update_data(time=time_obj)
        await message.answer("Введите комментарии (или '-' если нет):")
        await state.set_state(ServiceRecordStates.waiting_for_comments)
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ:")

@router.message(ServiceRecordStates.waiting_for_comments)
async def process_comments_and_send(message: Message, state: FSMContext, bot):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    comments = message.text if message.text != "-" else "Комментариев нет"
    data = await state.get_data()
    client_id = data["client_telegram_id"]
    service_name = data["service_name"]
    cost = data["cost"]
    address = data["address"]
    date_obj = data["date"]
    time_obj = data["time"]

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

    try:
        chat = await bot.get_chat(client_id)
        client_name = f"{chat.first_name} {chat.last_name or ''}".strip()
    except Exception:
        client_name = "Клиент"
    
    record_text = (
        f"📄 <b>Новая запись на услугу</b>\n\n"
        f"🔹 Услуга: {service_name}\n"
        f"🔹 Стоимость: {cost} руб.\n"
        f"🔹 Клиент: {client_name} (ID: {client_id})\n"
        f"🔹 Адрес: {address}\n"
        f"🔹 Дата: {date_obj.strftime('%d.%m.%Y')}\n"
        f"🔹 Время: {time_obj.strftime('%H:%M')}\n"
        f"🔹 Комментарии: {comments}"
    )

    if len(record_text) > 4000:
        record_text = record_text[:3997] + "..."

    # === Для МАСТЕРА: отправка + сохранение как ПРОЧИТАННОЕ ===
    try:
        await message.answer(record_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка отправки мастеру: {e}")
    
    # Импортируем здесь (чтобы избежать циклического импорта)
    from database import create_read_notification
    await create_read_notification(
        telegram_id=message.from_user.id,
        role="provider",
        message_text=record_text
    )

    # === Для КЛИЕНТА: отправка + сохранение как НЕПРОЧИТАННОЕ ===
    if client_id != message.from_user.id:
        try:
            await bot.send_message(client_id, record_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки клиенту: {e}")
        await create_notification(
            telegram_id=client_id,
            role="client",
            message_text=record_text
        )

    # Подтверждение
    if client_id != message.from_user.id:
        await message.answer("✅ Запись успешно отправлена клиенту!")
    else:
        await message.answer("✅ Запись сохранена.")

    # Возвращаемся в меню
    current_data = await state.get_data()
    role = current_data.get("user_role", "client")
    await state.clear()
    await state.update_data(user_role=role)
    menu_kb = provider_menu_keyboard if role == "provider" else client_menu_keyboard
    await message.answer("Вы вернулись в меню.", reply_markup=menu_kb())