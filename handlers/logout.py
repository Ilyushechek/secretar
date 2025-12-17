# handlers/logout.py

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard
from database import get_unread_count, is_user_registered  

router = Router()

async def logout(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    registered = await is_user_registered(telegram_id)  # ← проверяем регистрацию
    await state.clear()
    await message.answer(
        "Вы вышли из аккаунта.", 
        reply_markup=main_menu_keyboard(is_registered=registered)
    )

@router.message(F.text == "Выйти из аккаунта")
async def logout_account(message: Message, state: FSMContext):
    await logout(message, state)

@router.message(F.text == "В меню")
async def back_to_menu(message: Message, state: FSMContext):
    await logout(message, state)