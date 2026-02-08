"""
handlers/start.py
=================
Обработчик команды /start и главного меню.
Показывает разные варианты меню в зависимости от статуса регистрации.
"""

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard
from database import is_user_registered, get_unread_count

# Создаём роутер для обработки команды /start
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start.
    
    Показывает главное меню:
    - Незарегистрированным: только кнопка "Зарегистрироваться"
    - Зарегистрированным: кнопки входа с счётчиками уведомлений.
    
    Args:
        message: Входящее сообщение от пользователя
        state: Контекст состояния пользователя
    """
    # Получаем ID пользователя из сообщения
    telegram_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    registered = await is_user_registered(telegram_id)
    
    if registered:
        # Для зарегистрированных пользователей получаем счётчики уведомлений
        client_count = await get_unread_count(telegram_id, "client")
        provider_count = await get_unread_count(telegram_id, "provider")
        
        # Показываем меню с кнопками входа и счётчиками
        await message.answer(
            "Выберите действие:", 
            reply_markup=main_menu_keyboard(
                is_registered=True,
                client_count=client_count,
                provider_count=provider_count
            )
        )
    else:
        # Для незарегистрированных — только кнопка регистрации
        await message.answer(
            "Добро пожаловать! Зарегистрируйтесь, чтобы начать.",
            reply_markup=main_menu_keyboard(is_registered=False)
        )
    
    # Очищаем состояние пользователя
    await state.clear()