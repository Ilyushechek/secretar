"""
handlers/logout.py
==================
Обработчик выхода из аккаунта и возврата в меню роли
НЕ зависит от других обработчиков (чтобы избежать циклических импортов)
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard, client_menu_keyboard, provider_menu_keyboard
from database import is_user_registered, get_unread_count

router = Router()


async def return_to_role_menu(message: Message, state: FSMContext, role: str = None):
    """
    Возвращает пользователя в меню его роли (клиент/мастер)
    Если роль не указана — определяет из состояния или данных пользователя
    
    Args:
        message (Message): Сообщение для ответа
        state (FSMContext): Контекст состояния
        role (str, optional): 'client' или 'provider'
    """
    # Если роль не передана — получаем из состояния
    if not role:
        data = await state.get_data()
        role = data.get("user_role")
    
    # Если роль всё ещё неизвестна — определяем по наличию уведомлений
    if not role:
        telegram_id = message.from_user.id
        client_count = await get_unread_count(telegram_id, "client")
        provider_count = await get_unread_count(telegram_id, "provider")
        
        # Определяем роль по количеству уведомлений (эвристика)
        if provider_count > 0 and client_count == 0:
            role = "provider"
        elif client_count > 0 and provider_count == 0:
            role = "client"
        # Если оба нули или оба есть — возвращаем в главное меню
        else:
            registered = await is_user_registered(telegram_id)
            if registered:
                await message.answer(
                    "Выберите роль для входа:",
                    reply_markup=main_menu_keyboard(
                        is_registered=True,
                        client_count=client_count,
                        provider_count=provider_count
                    )
                )
            else:
                await message.answer(
                    "Вы в главном меню.",
                    reply_markup=main_menu_keyboard(is_registered=False)
                )
            await state.clear()
            return
    
    # Возвращаем в меню роли
    if role == "provider":
        await message.answer("Вы в меню мастера.", reply_markup=provider_menu_keyboard())
    else:
        await message.answer("Вы в меню клиента.", reply_markup=client_menu_keyboard())
    
    # Сохраняем роль в состоянии для будущих операций
    await state.update_data(user_role=role)


@router.message(F.text == "Выйти из аккаунта")
async def logout_account(message: Message, state: FSMContext):
    """
    Полный выход из аккаунта — в главное меню
    """
    telegram_id = message.from_user.id
    registered = await is_user_registered(telegram_id)
    
    if registered:
        client_count = await get_unread_count(telegram_id, "client")
        provider_count = await get_unread_count(telegram_id, "provider")
        await message.answer(
            "Вы вышли из аккаунта.",
            reply_markup=main_menu_keyboard(
                is_registered=True,
                client_count=client_count,
                provider_count=provider_count
            )
        )
    else:
        await message.answer(
            "Вы в главном меню.",
            reply_markup=main_menu_keyboard(is_registered=False)
        )
    
    await state.clear()


@router.message(F.text == "В меню")
async def back_to_menu(message: Message, state: FSMContext):
    """
    Возврат в меню текущей роли (не полный выход!)
    """
    await return_to_role_menu(message, state)