"""
handlers/provider_services.py
==============================
Управление услугами мастера
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import ServiceManagementStates
from database import (
    get_provider_services,
    add_provider_service,
    delete_provider_service
)
from keyboards import (
    provider_menu_keyboard,
    cancel_inline_keyboard,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from handlers.logout import return_to_role_menu  # ← ПРАВИЛЬНЫЙ ИМПОРТ ФУНКЦИИ

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


def get_services_keyboard(services: list) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру со списком услуг для управления"""
    buttons = []
    
    for srv in services:
        price_tag = f" 💰{srv['price_range']}" if srv['price_range'] else ""
        btn_text = f"{srv['service_name']}{price_tag}"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text[:30] + "..." if len(btn_text) > 30 else btn_text,
                callback_data=f"srv_action_{srv['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить услугу", callback_data="srv_add"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="srv_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "🔧 Мои услуги")
async def show_provider_services(message: Message, state: FSMContext):
    """
    Показывает список услуг мастера для управления
    """
    services = await get_provider_services(message.from_user.id)
    
    if not services:
        await message.answer(
            "У вас пока нет сохранённых услуг.\n"
            "Добавьте первую услугу для поиска клиентами.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить услугу", callback_data="srv_add")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="srv_menu")]
            ])
        )
        return
    
    await message.answer(
        "Ваши услуги:\n"
        "Выберите услугу для управления:",
        reply_markup=get_services_keyboard(services)
    )


@router.callback_query(F.data == "srv_add")
async def start_add_service(callback: CallbackQuery, state: FSMContext):
    """Начало добавления новой услуги"""
    await callback.answer()
    await callback.message.edit_text(
        "Введите название услуги:\n"
        "(Например: Маникюр, Ремонт сантехники, Массаж)",
        reply_markup=cancel_inline_keyboard()  # ← ИСПРАВЛЕНО
    )
    await state.set_state(ServiceManagementStates.waiting_for_service_name)


@router.message(ServiceManagementStates.waiting_for_service_name)
async def process_service_name(message: Message, state: FSMContext):
    """Обработка названия услуги"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="provider")
        return
    
    await state.update_data(service_name=message.text.strip())
    await message.answer(
        "Введите описание услуги (или '-' если нет):\n"
        "(Например: Классический маникюр с покрытием гель-лаком)",
        reply_markup=provider_menu_keyboard()  # ← Обычная клавиатура для нового сообщения
    )
    await state.set_state(ServiceManagementStates.waiting_for_description)


@router.message(ServiceManagementStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания услуги"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="provider")
        return
    
    description = None if message.text.strip() == '-' else message.text.strip()
    await state.update_data(description=description)
    await message.answer(
        "Введите диапазон цен (или '-' если нет):\n"
        "(Например: 1500-3000 или от 2000)",
        reply_markup=provider_menu_keyboard()  # ← Обычная клавиатура для нового сообщения
    )
    await state.set_state(ServiceManagementStates.waiting_for_price)


@router.message(ServiceManagementStates.waiting_for_price)
async def process_price_and_save(message: Message, state: FSMContext):
    """Обработка цены и сохранение услуги"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="provider")
        return
    
    price_range = None if message.text.strip() == '-' else message.text.strip()
    data = await state.get_data()
    
    # Сохраняем услугу
    await add_provider_service(
        provider_id=message.from_user.id,
        service_name=data['service_name'],
        description=data.get('description'),
        price_range=price_range
    )
    
    await message.answer(
        f"✅ Услуга добавлена!\n"
        f"Название: {data['service_name']}\n"
        f"{'Описание: ' + data['description'] if data.get('description') else ''}\n"
        f"{'Цены: ' + price_range if price_range else ''}",
        reply_markup=provider_menu_keyboard()
    )
    await state.clear()


@router.callback_query(F.data.startswith("srv_action_"))
async def service_action_menu(callback: CallbackQuery, state: FSMContext):
    """Меню действий с услугой (удалить)"""
    await callback.answer()
    
    service_id = int(callback.data.split("_")[-1])
    await state.update_data(current_service_id=service_id)
    
    await callback.message.edit_text(
        "Выберите действие с услугой:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"srv_delete_{service_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="srv_back")]
        ])
    )


@router.callback_query(F.data.startswith("srv_delete_"))
async def delete_service_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления услуги"""
    await callback.answer()
    
    service_id = int(callback.data.split("_")[-1])
    await state.update_data(service_to_delete=service_id)
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить эту услугу?\n"
        "Это может повлиять на поиск клиентами.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data="srv_confirm_delete")],
            [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="srv_back")]
        ])
    )


@router.callback_query(F.data == "srv_confirm_delete")
async def delete_service(callback: CallbackQuery, state: FSMContext):
    """Удаление услуги"""
    await callback.answer()
    
    data = await state.get_data()
    service_id = data.get('service_to_delete')
    
    if not service_id:
        await callback.message.edit_text(
            "❌ Ошибка: услуга не выбрана.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="srv_menu")]
            ])
        )
        return
    
    try:
        await delete_provider_service(service_id, callback.from_user.id)
        await callback.message.edit_text(
            "✅ Услуга удалена!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="srv_menu")]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка удаления услуги: {e}")
        await callback.message.edit_text(
            "❌ Не удалось удалить услугу.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="srv_menu")]
            ])
        )


@router.callback_query(F.data == "srv_back")
async def back_to_services_list(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку услуг"""
    await callback.answer()
    
    services = await get_provider_services(callback.from_user.id)
    await callback.message.edit_text(
        "Ваши услуги:",
        reply_markup=get_services_keyboard(services)
    )


@router.callback_query(F.data == "srv_menu")
@router.callback_query(F.data == "cancel_action")  # ← Обработка отмены
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню мастера"""
    await callback.answer()
    await callback.message.edit_text(
        "Вы вернулись в меню мастера.",
        reply_markup=provider_menu_keyboard()
    )