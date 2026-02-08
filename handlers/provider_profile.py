"""
handlers/provider_profile.py
============================
Управление фото профиля мастера
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import ProfilePhotoStates
from database import update_provider_profile_photo, get_provider_profile_photo
from keyboards import (
    provider_menu_keyboard,
    cancel_inline_keyboard,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.types import InputMediaPhoto
from handlers.logout import return_to_role_menu  # ← ПРАВИЛЬНЫЙ ИМПОРТ ФУНКЦИИ

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "📸 Фото профиля")
async def show_profile_photo_menu(message: Message, state: FSMContext):
    """Меню управления фото профиля"""
    # Получаем текущее фото
    photo_file_id = await get_provider_profile_photo(message.from_user.id)
    
    if photo_file_id:
        # Показываем текущее фото с кнопками управления
        await message.answer_photo(
            photo=photo_file_id,
            caption="Ваше текущее фото профиля.\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Заменить фото", callback_data="change_profile_photo")],
                [InlineKeyboardButton(text="🗑️ Удалить фото", callback_data="delete_profile_photo")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="profile_menu")]
            ])
        )
    else:
        # Нет фото — предложить загрузку
        await message.answer(
            "У вас нет фото профиля.\n"
            "Загрузите фото, чтобы клиенты видели вас при поиске.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить фото", callback_data="add_profile_photo")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="profile_menu")]
            ])
        )


@router.callback_query(F.data == "add_profile_photo")
@router.callback_query(F.data == "change_profile_photo")
async def start_photo_upload(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки нового фото профиля"""
    await callback.answer()
    await callback.message.edit_text(
        "Отправьте новое фото профиля (лучше портретное, хорошего качества):",
        reply_markup=cancel_inline_keyboard()
    )
    await state.set_state(ProfilePhotoStates.waiting_for_photo)


@router.message(ProfilePhotoStates.waiting_for_photo, F.photo)
async def save_profile_photo(message: Message, state: FSMContext):
    """Сохранение фото профиля"""
    # Берём фото максимального разрешения
    photo = message.photo[-1]
    
    # Сохраняем в БД
    await update_provider_profile_photo(
        provider_id=message.from_user.id,
        photo_file_id=photo.file_id
    )
    
    # Подтверждение с предпросмотром
    await message.answer_photo(
        photo=photo.file_id,
        caption="✅ Фото профиля обновлено!\nТеперь клиенты будут видеть его при поиске.",
        reply_markup=provider_menu_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "delete_profile_photo")
async def delete_profile_photo_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления фото профиля"""
    await callback.answer()
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить фото профиля?\n"
        "Клиенты не будут видеть ваше фото при поиске.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete_photo")],
            [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="profile_menu")]
        ])
    )


@router.callback_query(F.data == "confirm_delete_photo")
async def delete_profile_photo(callback: CallbackQuery, state: FSMContext):
    """Удаление фото профиля"""
    await callback.answer()
    
    # Обновляем БД (очищаем поле)
    await update_provider_profile_photo(
        provider_id=callback.from_user.id,
        photo_file_id=None
    )
    
    await callback.message.edit_text(
        "✅ Фото профиля удалено.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="profile_menu")]
        ])
    )


@router.callback_query(F.data == "profile_menu")
async def back_to_provider_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню мастера"""
    await callback.answer()
    from handlers.logout import return_to_role_menu
    await return_to_role_menu(callback.message, state, role="provider")