"""
handlers/password_reset.py
==========================
Обработчик сброса пароля через email с 6-значным кодом подтверждения
"""

import bcrypt
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from FSMstates import PasswordResetStates
from database import (
    is_user_registered,
    get_user_email,
    generate_reset_code,
    verify_reset_code,
    clear_reset_code,
    update_password
)
from email_utils import send_reset_code_email
from keyboards import cancel_menu_keyboard, main_menu_keyboard
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки сброса пароля
router = Router()


@router.message(F.text == "Сбросить пароль")
async def start_password_reset(message: Message, state: FSMContext):
    """
    Начало процесса сброса пароля
    
    Доступно из главного меню для зарегистрированных пользователей
    Запрашивает email для отправки кода
    
    Args:
        message (Message): Входящее сообщение
        state (FSMContext): Контекст состояния
    """
    # Получаем ID пользователя
    telegram_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await is_user_registered(telegram_id):
        await message.answer("Вы не зарегистрированы. Сначала зарегистрируйтесь.")
        return
    
    # Запрашиваем email
    await message.answer(
        "Введите ваш email для получения кода:", 
        reply_markup=cancel_menu_keyboard()
    )
    
    # Устанавливаем состояние ожидания email
    await state.set_state(PasswordResetStates.waiting_for_email)


@router.message(PasswordResetStates.waiting_for_email)
async def process_reset_email(message: Message, state: FSMContext):
    """
    Обработка ввода email для сброса пароля
    
    Проверяет совпадение с зарегистрированным email
    Генерирует и отправляет 6-значный код
    
    Args:
        message (Message): Сообщение с email
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Получаем ID пользователя
    telegram_id = message.from_user.id
    
    # Получаем зарегистрированный email из БД
    saved_email = await get_user_email(telegram_id)
    
    # Проверяем совпадение email (регистронезависимо)
    if not saved_email or saved_email.lower() != message.text.strip().lower():
        await message.answer(
            "Email не совпадает с зарегистрированным. Попробуйте снова:", 
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Генерируем и отправляем код подтверждения
    try:
        code = await generate_reset_code(telegram_id)
        await send_reset_code_email(saved_email, code)
        await message.answer("Код отправлен на ваш email. Введите его:")
        await state.set_state(PasswordResetStates.waiting_for_code)
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        await message.answer("Не удалось отправить код. Попробуйте позже.")


@router.message(PasswordResetStates.waiting_for_code)
async def process_reset_code(message: Message, state: FSMContext):
    """
    Обработка ввода кода подтверждения
    
    Проверяет валидность кода (срок действия 10 минут)
    При успехе - запрашивает новый пароль
    
    Args:
        message (Message): Сообщение с кодом
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Получаем ID пользователя
    telegram_id = message.from_user.id
    
    # Проверяем код
    if await verify_reset_code(telegram_id, message.text.strip()):
        # Код верный - очищаем его и запрашиваем новый пароль
        await clear_reset_code(telegram_id)
        await message.answer("Код подтверждён. Введите новый пароль (минимум 4 символа):")
        await state.set_state(PasswordResetStates.waiting_for_new_password)
    else:
        # Код неверный или просрочен
        await message.answer(
            "Неверный или просроченный код. Попробуйте снова:", 
            reply_markup=cancel_menu_keyboard()
        )


@router.message(PasswordResetStates.waiting_for_new_password)
async def enter_new_password(message: Message, state: FSMContext):
    """
    Ввод нового пароля
    
    Проверяет длину (минимум 4 символа)
    
    Args:
        message (Message): Сообщение с новым паролем
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Проверяем длину пароля
    if len(message.text) < 4:
        await message.answer(
            "Пароль слишком короткий:", 
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Сохраняем новый пароль в состоянии
    await state.update_data(new_password=message.text)
    
    # Запрашиваем подтверждение
    await message.answer("Повторите новый пароль:", reply_markup=cancel_menu_keyboard())
    await state.set_state(PasswordResetStates.waiting_for_confirm_new_password)


@router.message(PasswordResetStates.waiting_for_confirm_new_password)
async def confirm_new_password(message: Message, state: FSMContext):
    """
    Подтверждение нового пароля
    
    Сравнивает пароли и сохраняет хэш в БД при совпадении
    
    Args:
        message (Message): Сообщение с подтверждением пароля
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    
    # Сравниваем пароли
    if data["new_password"] != message.text:
        await message.answer(
            "Пароли не совпадают. Введите новый пароль:", 
            reply_markup=cancel_menu_keyboard()
        )
        await state.set_state(PasswordResetStates.waiting_for_new_password)
        return
    
    # Пароли совпадают - хэшируем и сохраняем в БД
    password_hash = bcrypt.hashpw(
        data["new_password"].encode(), 
        bcrypt.gensalt()
    ).decode()
    
    await update_password(message.from_user.id, password_hash)
    
    # Показываем завершающее сообщение
    await message.answer(
        "✅ Пароль успешно изменён!", 
        reply_markup=main_menu_keyboard(is_registered=True)
    )
    
    # Очищаем состояние
    await state.clear()