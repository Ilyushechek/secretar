# handlers/chat.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
from FSMstates import ClientChatStates, ProviderChatStates
from database import (
    get_user_telegram_id_by_code,
    create_chat,
    get_active_chat_by_client,
    get_active_chat_by_provider,
    close_chat
)
from keyboards import (
    client_menu_keyboard,
    provider_menu_keyboard,
    client_chat_active_keyboard,
    provider_chat_active_keyboard,
    chat_request_inline
)

router = Router()

async def close_chat_and_offer_record(chat_id: int, provider_id: int, client_id: int, bot):
    await close_chat(chat_id)
    try:
        await bot.send_message(
            provider_id,
            "Чат завершён.\nХотите добавить запись об услуге?",
            reply_markup=provider_menu_keyboard()
        )
    except TelegramForbiddenError:
        pass
    try:
        await bot.send_message(client_id, "Чат с мастером завершён.", reply_markup=client_menu_keyboard())
    except TelegramForbiddenError:
        pass

@router.message(F.text == "Связаться с мастером")
async def start_contact(message: Message, state: FSMContext):
    active_chat = await get_active_chat_by_client(message.from_user.id)
    if active_chat:
        await message.answer("У вас уже есть активный чат с мастером.")
        return
    await message.answer("Введите 6-значный ID мастера:")
    await state.set_state(ClientChatStates.waiting_for_provider_id)

@router.message(ClientChatStates.waiting_for_provider_id)
async def process_provider_id(message: Message, state: FSMContext, bot):
    user_code = message.text.strip()
    if not user_code.isdigit() or len(user_code) != 6:
        await message.answer("Неверный формат ID. Введите 6 цифр:")
        return
    provider_telegram_id = await get_user_telegram_id_by_code(user_code)
    if not provider_telegram_id:
        await message.answer("Мастер с таким ID не найден. Попробуйте снова:")
        return
    if provider_telegram_id == message.from_user.id:
        await message.answer("Вы не можете связаться сами с собой.")
        return
    chat_id = await create_chat(message.from_user.id, provider_telegram_id)
    try:
        await bot.send_message(
            provider_telegram_id,
            f"🔔 Запрос от клиента (ID: {user_code})\nПринять?",
            reply_markup=chat_request_inline(chat_id)
        )
        await message.answer("Запрос отправлен мастеру. Ожидайте ответа.")
    except TelegramForbiddenError:
        await message.answer("Не удалось отправить запрос: мастер заблокировал бота.")
        await close_chat(chat_id)
        return
    await state.set_state(ClientChatStates.in_chat)
    await state.update_data(chat_id=chat_id, partner_id=provider_telegram_id)
    await message.answer("Чат начат. Нажмите «Завершить чат», чтобы остановить общение.", reply_markup=client_chat_active_keyboard())

@router.callback_query(F.data.startswith("accept_chat_"))
async def accept_chat(callback: CallbackQuery, state: FSMContext, bot):
    chat_id = int(callback.data.split("_")[-1])
    active_chat = await get_active_chat_by_provider(callback.from_user.id)
    if not active_chat or active_chat["id"] != chat_id:
        await callback.answer("Чат уже закрыт или не найден.", show_alert=True)
        return
    client_id = active_chat["client_telegram_id"]
    try:
        await bot.send_message(client_id, "✅ Мастер принял ваш запрос! Теперь вы можете писать друг другу.")
        await bot.send_message(
            callback.from_user.id,
            "✅ Вы приняли запрос! Теперь вы можете писать клиенту.\nНажмите «Завершить чат», чтобы остановить общение.",
            reply_markup=provider_chat_active_keyboard()
        )
    except TelegramForbiddenError:
        await callback.answer("Клиент заблокировал бота.", show_alert=True)
        await close_chat(chat_id)
        return
    await state.set_state(ProviderChatStates.in_chat)
    await state.update_data(chat_id=chat_id, partner_id=client_id)
    await callback.answer()
    await callback.message.edit_text("Чат активен.")

@router.callback_query(F.data.startswith("reject_chat_"))
async def reject_chat(callback: CallbackQuery, bot):
    chat_id = int(callback.data.split("_")[-1])
    active_chat = await get_active_chat_by_provider(callback.from_user.id)
    if active_chat and active_chat["id"] == chat_id:
        client_id = active_chat["client_telegram_id"]
        try:
            await bot.send_message(client_id, "❌ Мастер отклонил ваш запрос.", reply_markup=client_menu_keyboard())
        except TelegramForbiddenError:
            pass
        await close_chat(chat_id)
    await callback.answer("Запрос отклонён.", show_alert=True)
    await callback.message.edit_text("Запрос отклонён.")

# === ИСПРАВЛЕНО: сохранение роли при завершении чата ===

@router.message(ClientChatStates.in_chat, F.text == "Завершить чат")
async def client_end_chat(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    partner_id = data.get("partner_id")
    if chat_id and partner_id:
        await close_chat_and_offer_record(chat_id, partner_id, message.from_user.id, bot)
    
    # Очищаем состояние, но сохраняем роль
    current_data = await state.get_data()
    role = current_data.get("user_role")
    await state.clear()
    if role:
        await state.update_data(user_role=role)
    
    await message.answer("Вы вышли из чата.", reply_markup=client_menu_keyboard())

@router.message(ProviderChatStates.in_chat, F.text == "Завершить чат")
async def provider_end_chat(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    partner_id = data.get("partner_id")
    if chat_id and partner_id:
        await close_chat_and_offer_record(chat_id, message.from_user.id, partner_id, bot)
    
    # Очищаем состояние, но сохраняем роль
    current_data = await state.get_data()
    role = current_data.get("user_role")
    await state.clear()
    if role:
        await state.update_data(user_role=role)
    
    await message.answer("Вы завершили чат.", reply_markup=provider_menu_keyboard())

@router.message(ClientChatStates.in_chat)
async def forward_from_client(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    partner_id = data.get("partner_id")
    if not partner_id:
        await message.answer("Ошибка сессии.", reply_markup=client_menu_keyboard())
        await state.clear()
        return
    try:
        await bot.send_message(partner_id, f"Сообщение от клиента:\n\n{message.text}")
    except TelegramForbiddenError:
        chat_id = data.get("chat_id")
        if chat_id:
            await close_chat_and_offer_record(chat_id, partner_id, message.from_user.id, bot)
        await message.answer("Мастер заблокировал бота. Чат завершён.", reply_markup=client_menu_keyboard())
        # Сохраняем роль
        current_data = await state.get_data()
        role = current_data.get("user_role")
        await state.clear()
        if role:
            await state.update_data(user_role=role)

@router.message(ProviderChatStates.in_chat)
async def forward_from_provider(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    partner_id = data.get("partner_id")
    if not partner_id:
        await message.answer("Ошибка сессии.", reply_markup=provider_menu_keyboard())
        await state.clear()
        return
    try:
        await bot.send_message(partner_id, f"Сообщение от мастера:\n\n{message.text}")
    except TelegramForbiddenError:
        chat_id = data.get("chat_id")
        if chat_id:
            await close_chat_and_offer_record(chat_id, message.from_user.id, partner_id, bot)
        await message.answer("Клиент заблокировал бота. Чат завершён.", reply_markup=provider_menu_keyboard())
        # Сохраняем роль
        current_data = await state.get_data()
        role = current_data.get("user_role")
        await state.clear()
        if role:
            await state.update_data(user_role=role)