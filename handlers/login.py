import bcrypt
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from FSMstates import LoginStates, PasswordResetStates, AuthStates
from database import get_password_hash, is_user_registered, get_unread_notifications, mark_notifications_as_read
from keyboards import client_menu_keyboard, provider_menu_keyboard, password_reset_inline

router = Router()
MAX_LOGIN_ATTEMPTS = 3

@router.message(F.text.startswith(("Войти как клиент", "Войти как предоставитель услуги")))
async def login_start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    if not await is_user_registered(telegram_id):
        await message.answer("Вы не зарегистрированы. Сначала зарегистрируйтесь.")
        return
    
    role = "provider" if message.text.startswith("Войти как предоставитель") else "client"
    
    # Сохраняем роль, но НЕ показываем уведомления
    await state.update_data(role=role, login_attempts=0, user_role=role)
    await state.set_state(LoginStates.waiting_for_password)
    await message.answer("Введите ваш пароль:")

@router.message(LoginStates.waiting_for_password)
async def login_check_password(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    password = message.text
    stored_hash = await get_password_hash(telegram_id)
    data = await state.get_data()
    attempts = data.get("login_attempts", 0)
    
    if not stored_hash or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        attempts += 1
        await state.update_data(login_attempts=attempts)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            await message.answer(
                f"❌ Неверный пароль. Достигнуто {attempts} неудачных попыток.\n"
                "Хотите сбросить пароль?",
                reply_markup=password_reset_inline()
            )
        else:
            await message.answer(f"Неверный пароль. Попытка {attempts} из {MAX_LOGIN_ATTEMPTS}. Попробуйте снова:")
        return

    # УСПЕШНЫЙ ВХОД
    role = data["role"]
    role_name = "предоставитель услуги" if role == "provider" else "клиент"
    await state.set_state(AuthStates.authorized)
    
    # Показываем уведомления ПОСЛЕ входа
    unread_msgs = await get_unread_notifications(telegram_id, role)
    if unread_msgs:
        await message.answer("У вас есть непрочитанные уведомления:")
        for msg in unread_msgs:
            text = msg["message_text"]
            if len(text) > 4000:
                text = text[:3997] + "..."
            try:
                await message.answer(text, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Ошибка отправки уведомления: {e}")
                await message.answer(text.replace("<", "").replace(">", ""), parse_mode=None)
        await mark_notifications_as_read(telegram_id, role)

    # Показываем меню
    if role == "provider":
        await message.answer(f"✅ Добро пожаловать, {role_name}!", reply_markup=provider_menu_keyboard())
    else:
        await message.answer(f"✅ Добро пожалуйста, {role_name}!", reply_markup=client_menu_keyboard())

@router.callback_query(F.data == "reset_password_from_login")
async def reset_password_from_login(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.edit_text("Вы можете сбросить пароль.\nВведите ваш текущий пароль:")
    except TelegramBadRequest:
        await callback.message.answer("Вы можете сбросить пароль.\nВведите ваш текущий пароль:")
    await state.set_state(PasswordResetStates.waiting_for_current_password)