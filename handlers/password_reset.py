# handlers/password_reset.py

import bcrypt
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from FSMstates import PasswordResetStates, AuthStates
from database import (
    get_user_email,
    generate_reset_code,
    verify_reset_code,
    clear_reset_code,
    update_password
)
from email_utils import send_reset_code_email
from keyboards import cancel_menu_keyboard, main_menu_keyboard

router = Router()

@router.message(F.text == "Сбросить пароль")
async def start_password_reset(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != AuthStates.authorized.state:
        await message.answer("Сначала войдите в аккаунт.")
        return
    await message.answer("Введите ваш email для получения кода:", reply_markup=cancel_menu_keyboard())
    await state.set_state(PasswordResetStates.waiting_for_email)

@router.message(PasswordResetStates.waiting_for_email)
async def process_reset_email(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    
    telegram_id = message.from_user.id
    saved_email = await get_user_email(telegram_id)
    
    if not saved_email or saved_email != message.text.strip():
        await message.answer("Email не совпадает с зарегистрированным. Попробуйте снова:", reply_markup=cancel_menu_keyboard())
        return

    try:
        code = await generate_reset_code(telegram_id)
        await send_reset_code_email(saved_email, code)
        await message.answer("Код отправлен на ваш email. Введите его:")
        await state.set_state(PasswordResetStates.waiting_for_code)
    except Exception as e:
        await message.answer("Не удалось отправить код. Попробуйте позже.")
        logging.error(f"Ошибка отправки email: {e}")

@router.message(PasswordResetStates.waiting_for_code)
async def process_reset_code(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    
    telegram_id = message.from_user.id
    if await verify_reset_code(telegram_id, message.text.strip()):
        await clear_reset_code(telegram_id)
        await message.answer("Код подтверждён. Введите новый пароль (минимум 4 символа):")
        await state.set_state(PasswordResetStates.waiting_for_new_password)
    else:
        await message.answer("Неверный или просроченный код. Попробуйте снова:", reply_markup=cancel_menu_keyboard())

@router.message(PasswordResetStates.waiting_for_new_password)
async def enter_new_password(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    if len(message.text) < 4:
        await message.answer("Пароль слишком короткий:", reply_markup=cancel_menu_keyboard())
        return
    await state.update_data(new_password=message.text)
    await message.answer("Повторите новый пароль:", reply_markup=cancel_menu_keyboard())
    await state.set_state(PasswordResetStates.waiting_for_confirm_new_password)

@router.message(PasswordResetStates.waiting_for_confirm_new_password)
async def confirm_new_password(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    data = await state.get_data()
    if data["new_password"] != message.text:
        await message.answer("Пароли не совпадают. Введите новый пароль:", reply_markup=cancel_menu_keyboard())
        await state.set_state(PasswordResetStates.waiting_for_new_password)
        return
    password_hash = bcrypt.hashpw(data["new_password"].encode(), bcrypt.gensalt()).decode()
    await update_password(message.from_user.id, password_hash)
    await message.answer("✅ Пароль успешно изменён!", reply_markup=main_menu_keyboard())
    await state.clear()