# handlers/start.py

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard
from database import get_unread_count, is_user_registered

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    registered = await is_user_registered(telegram_id)  # ← проверка
    await state.clear()
    await message.answer(
        "Привет! Выберите действие:", 
        reply_markup=main_menu_keyboard(is_registered=registered)
    )