"""
handlers/login.py
=================
Обработчик входа в систему по ролям (клиент/мастер).
Проверяет пароль и показывает уведомления ПОСЛЕ успешного входа.
"""

import bcrypt
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from FSMstates import LoginStates, AuthStates
from database import (
    get_password_hash, 
    is_user_registered, 
    get_unread_notifications, 
    mark_notifications_as_read
)
from keyboards import client_menu_keyboard, provider_menu_keyboard, password_reset_inline
from handlers.logout import return_to_role_menu  # ← ПРАВИЛЬНЫЙ ИМПОРТ ФУНКЦИИ

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки входа
router = Router()

# Максимальное количество попыток ввода пароля
MAX_LOGIN_ATTEMPTS = 3


@router.message(F.text.startswith(("Войти как клиент", "Войти как предоставитель услуги")))
async def login_start(message: Message, state: FSMContext):
    """
    Начало процесса входа.
    
    Определяет роль пользователя по тексту кнопки.
    Запрашивает пароль.
    """
    # Получаем ID пользователя
    telegram_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await is_user_registered(telegram_id):
        await message.answer("Вы не зарегистрированы. Сначала зарегистрируйтесь.")
        return
    
    # Определяем роль по тексту кнопки
    if message.text.startswith("Войти как предоставитель"):
        role = "provider"
    else:
        role = "client"
    
    # Сохраняем роль и сбрасываем счётчик попыток
    await state.update_data(
        role=role, 
        login_attempts=0, 
        user_role=role
    )
    
    # Устанавливаем состояние ожидания пароля
    await state.set_state(LoginStates.waiting_for_password)
    
    # Запрашиваем пароль
    await message.answer("Введите ваш пароль:")


@router.message(LoginStates.waiting_for_password)
async def login_check_password(message: Message, state: FSMContext):
    """
    Проверка пароля при входе
    
    Сравнивает введённый пароль с хэшем в БД
    При успехе - показывает уведомления и меню роли
    При неудаче - увеличивает счётчик попыток
    
    Args:
        message (Message): Сообщение с паролем
        state (FSMContext): Контекст состояния
    """
    # Получаем ID пользователя
    telegram_id = message.from_user.id
    
    # Получаем хэш пароля из БД
    stored_hash = await get_password_hash(telegram_id)
    
    # Получаем данные из состояния (роль, счётчик попыток)
    data = await state.get_data()
    attempts = data.get("login_attempts", 0)
    
    # Проверяем пароль (сравниваем хэши с помощью bcrypt)
    if not stored_hash or not bcrypt.checkpw(
        message.text.encode(),      # Введённый пароль в bytes
        stored_hash.encode()        # Сохранённый хэш в bytes
    ):
        # Пароль неверный - увеличиваем счётчик попыток
        attempts += 1
        await state.update_data(login_attempts=attempts)
        
        # Проверяем лимит попыток
        if attempts >= MAX_LOGIN_ATTEMPTS:
            # Превышен лимит - показываем кнопку сброса пароля
            from keyboards import password_reset_inline
            await message.answer(
                f"❌ Неверный пароль. Достигнуто {attempts} неудачных попыток.\n"
                "Хотите сбросить пароль?",
                reply_markup=password_reset_inline()
            )
        else:
            # Ещё есть попытки - просим ввести снова
            await message.answer(
                f"Неверный пароль. Попытка {attempts} из {MAX_LOGIN_ATTEMPTS}. "
                "Попробуйте снова:"
            )
        return
    
    # Пароль верный - успешный вход
    
    # Получаем роль из состояния
    role = data["role"]
    role_name = "предоставитель услуги" if role == "provider" else "клиент"
    
    # Устанавливаем состояние авторизованного пользователя
    await state.set_state(AuthStates.authorized)
    
    # ============================================================================
    # ПОКАЗ УВЕДОМЛЕНИЙ ТОЛЬКО ПОСЛЕ УСПЕШНОГО ВХОДА
    # ============================================================================
    
    # Получаем непрочитанные уведомления ТОЛЬКО для текущей роли
    unread_msgs = await get_unread_notifications(telegram_id, role)
    
    if unread_msgs:
        # Показываем заголовок
        await message.answer("У вас есть непрочитанные уведомления:")
        
        # Показываем каждое уведомление
        for msg in unread_msgs:
            text = msg["message_text"]
            
            # Ограничиваем длину сообщения (макс. 4000 символов для Telegram)
            if len(text) > 4000:
                text = text[:3997] + "..."
            
            try:
                # Пытаемся отправить с HTML-разметкой
                await message.answer(text, parse_mode="HTML")
            except Exception as e:
                # Если ошибка с HTML - отправляем как простой текст
                logger.error(f"Ошибка отправки уведомления: {e}")
                await message.answer(
                    text.replace("<", "").replace(">", ""), 
                    parse_mode=None
                )
        
        # Помечаем уведомления как прочитанные
        await mark_notifications_as_read(telegram_id, role)
    
    # ============================================================================
    # ПОКАЗ МЕНЮ В ЗАВИСИМОСТИ ОТ РОЛИ
    # ============================================================================
    
    if role == "provider":
        # Меню для мастера
        await message.answer(
            f"✅ Добро пожаловать, {role_name}!", 
            reply_markup=provider_menu_keyboard()
        )
    else:
        # Меню для клиента
        await message.answer(
            f"✅ Добро пожаловать, {role_name}!", 
            reply_markup=client_menu_keyboard()
        )