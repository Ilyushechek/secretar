# handlers/registration.py

import bcrypt
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from FSMstates import RegistrationStates
from database import is_user_registered, create_user, update_user_email
from keyboards import main_menu_keyboard, cancel_menu_keyboard

router = Router()

@router.message(F.text == "Зарегистрироваться")
async def register_start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    if await is_user_registered(telegram_id):
        await message.answer("Вы уже зарегистрированы!", reply_markup=main_menu_keyboard())
        return
    await state.update_data(telegram_id=telegram_id)
    await message.answer("Придумайте пароль (минимум 4 символа):", reply_markup=cancel_menu_keyboard())
    await state.set_state(RegistrationStates.waiting_for_password)

@router.message(RegistrationStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    if len(message.text) < 4:
        await message.answer("Пароль слишком короткий. Попробуйте ещё раз:", reply_markup=cancel_menu_keyboard())
        return
    await state.update_data(password=message.text)
    await message.answer("Повторите пароль:", reply_markup=cancel_menu_keyboard())
    await state.set_state(RegistrationStates.waiting_for_confirm_password)

@router.message(RegistrationStates.waiting_for_confirm_password)
async def process_confirm_password(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    data = await state.get_data()
    if data["password"] != message.text:
        await message.answer("Пароли не совпадают. Введите пароль заново:", reply_markup=cancel_menu_keyboard())
        await state.set_state(RegistrationStates.waiting_for_password)
        return
    
    # Запрашиваем email
    await message.answer("Введите ваш email:")
    await state.set_state(RegistrationStates.waiting_for_email)

@router.message(RegistrationStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    if message.text == "В меню":
        from handlers.logout import logout
        await logout(message, state)
        return
    
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("Неверный формат email. Попробуйте снова:")
        return

    data = await state.get_data()
    password_hash = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    user_code = await create_user(data["telegram_id"], password_hash)
    await update_user_email(data["telegram_id"], email)
    
    await message.answer(
        f"✅ Регистрация завершена!\nВаш персональный ID: <b>{user_code}</b>",
        reply_markup=main_menu_keyboard(is_registered=True),  # ← добавлен параметр
        parse_mode="HTML"
    )
    await state.clear() 