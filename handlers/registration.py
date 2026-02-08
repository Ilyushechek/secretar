"""
handlers/registration.py
========================
Обработчик процесса регистрации нового пользователя
Последовательность: пароль → подтверждение → имя → фамилия → email
"""

import bcrypt
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from FSMstates import RegistrationStates
from database import (
    is_user_registered, 
    create_user, 
    update_user_name, 
    update_user_email
)
from keyboards import main_menu_keyboard, cancel_menu_keyboard
from handlers.logout import return_to_role_menu

# Создаём роутер для обработки регистрации
router = Router()


@router.message(F.text == "Зарегистрироваться")
async def register_start(message: Message, state: FSMContext):
    """
    Начало процесса регистрации
    
    Проверяет, не зарегистрирован ли пользователь уже
    Если нет - запрашивает пароль
    
    Args:
        message (Message): Входящее сообщение
        state (FSMContext): Контекст состояния
    """
    # Получаем ID пользователя
    telegram_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    if await is_user_registered(telegram_id):
        # Если уже зарегистрирован - показываем меню с кнопками входа
        await message.answer(
            "Вы уже зарегистрированы!", 
            reply_markup=main_menu_keyboard(is_registered=True)
        )
        return
    
    # Сохраняем telegram_id в состоянии для последующих шагов
    await state.update_data(telegram_id=telegram_id)
    
    # Запрашиваем пароль
    await message.answer(
        "Придумайте пароль (минимум 4 символа):", 
        reply_markup=cancel_menu_keyboard()
    )
    
    # Устанавливаем состояние ожидания пароля
    await state.set_state(RegistrationStates.waiting_for_password)


@router.message(RegistrationStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """
    Обработка ввода пароля
    
    Проверяет длину пароля (минимум 4 символа)
    Если короткий - просит ввести заново
    
    Args:
        message (Message): Сообщение с паролем
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
            "Пароль слишком короткий. Попробуйте ещё раз:", 
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Сохраняем пароль в состоянии
    await state.update_data(password=message.text)
    
    # Запрашиваем подтверждение пароля
    await message.answer(
        "Повторите пароль:", 
        reply_markup=cancel_menu_keyboard()
    )
    
    # Устанавливаем состояние ожидания подтверждения
    await state.set_state(RegistrationStates.waiting_for_confirm_password)


@router.message(RegistrationStates.waiting_for_confirm_password)
async def process_confirm_password(message: Message, state: FSMContext):
    """
    Обработка подтверждения пароля
    
    Сравнивает введённые пароли
    Если не совпадают - возвращает на шаг ввода пароля
    
    Args:
        message (Message): Сообщение с подтверждением пароля
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Получаем сохранённые данные из состояния
    data = await state.get_data()
    
    # Сравниваем пароли
    if data["password"] != message.text:
        await message.answer(
            "Пароли не совпадают. Введите пароль заново:", 
            reply_markup=cancel_menu_keyboard()
        )
        # Возвращаемся к вводу пароля
        await state.set_state(RegistrationStates.waiting_for_password)
        return
    
    # Пароли совпадают - запрашиваем имя
    await message.answer("Введите ваше имя:")
    await state.set_state(RegistrationStates.waiting_for_first_name)


@router.message(RegistrationStates.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    """
    Обработка ввода имени
    
    Сохраняет имя и запрашивает фамилию
    
    Args:
        message (Message): Сообщение с именем
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Сохраняем имя в состоянии
    await state.update_data(first_name=message.text.strip())
    
    # Запрашиваем фамилию
    await message.answer("Введите вашу фамилию:")
    await state.set_state(RegistrationStates.waiting_for_last_name)


@router.message(RegistrationStates.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    """
    Обработка ввода фамилии
    
    Сохраняет фамилию и запрашивает email
    
    Args:
        message (Message): Сообщение с фамилией
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Сохраняем фамилию в состоянии
    await state.update_data(last_name=message.text.strip())
    
    # Запрашиваем email
    await message.answer("Введите ваш email:")
    await state.set_state(RegistrationStates.waiting_for_email)


@router.message(RegistrationStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    """
    Обработка ввода email
    
    Проверяет формат email (простая проверка на наличие @ и .)
    Сохраняет пользователя в БД и показывает завершающее сообщение
    
    Args:
        message (Message): Сообщение с email
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Простая проверка формата email
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("Неверный формат email. Попробуйте снова:")
        return
    
    # Получаем все сохранённые данные из состояния
    data = await state.get_data()
    
    # Хэшируем пароль с помощью bcrypt
    password_hash = bcrypt.hashpw(
        data["password"].encode(),  # Кодируем пароль в bytes
        bcrypt.gensalt()            # Генерируем "соль" для хэширования
    ).decode()  # Декодируем обратно в строку
    
    # Создаём пользователя в БД и получаем его 6-значный код
    user_code = await create_user(data["telegram_id"], password_hash)
    
    # Сохраняем имя и фамилию в БД
    await update_user_name(
        data["telegram_id"], 
        data["first_name"], 
        data["last_name"]
    )
    
    # Сохраняем email в БД
    await update_user_email(data["telegram_id"], email)
    
    # Показываем завершающее сообщение с кодом пользователя
    await message.answer(
        f"✅ Регистрация завершена!\nВаш персональный ID: <b>{user_code}</b>",
        reply_markup=main_menu_keyboard(is_registered=True),
        parse_mode="HTML"  # Включаем поддержку HTML-разметки
    )
    
    # Очищаем состояние пользователя
    await state.clear()