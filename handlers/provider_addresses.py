"""
handlers/provider_addresses.py
===============================
Управление адресами работы мастера
"""

"""
handlers/provider_addresses.py
===============================
Управление адресами работы мастера
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import AddressManagementStates
from database import (
    get_provider_addresses,
    add_provider_address,
    delete_provider_address,
    geocode_address
)
from keyboards import (
    provider_menu_keyboard,
    cancel_inline_keyboard,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from handlers.logout import return_to_role_menu  # ← ИСПРАВЛЕНО: правильный импорт

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


def get_addresses_keyboard(addresses: list) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру со списком адресов для управления"""
    buttons = []
    
    for addr in addresses:
        prefix = "⭐ " if addr['is_primary'] else ""
        btn_text = f"{prefix}{addr['address'][:30]}..." if len(addr['address']) > 30 else f"{prefix}{addr['address']}"
        buttons.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"addr_action_{addr['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить адрес", callback_data="addr_add"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="addr_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "📍 Адреса работы")
async def show_provider_addresses(message: Message, state: FSMContext):
    """
    Показывает список адресов мастера для управления
    """
    addresses = await get_provider_addresses(message.from_user.id)
    
    if not addresses:
        await message.answer(
            "У вас пока нет сохранённых адресов.\n"
            "Добавьте первый адрес для поиска клиентами.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить адрес", callback_data="addr_add")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="addr_menu")]
            ])
        )
        return
    
    await message.answer(
        "Ваши адреса работы:\n"
        "⭐ — основной адрес (используется для поиска)\n"
        "Выберите адрес для управления:",
        reply_markup=get_addresses_keyboard(addresses)
    )


@router.callback_query(F.data == "addr_add")
async def start_add_address(callback: CallbackQuery, state: FSMContext):
    """Начало добавления нового адреса"""
    await callback.answer()
    await callback.message.edit_text(
        "Введите адрес работы:\n"
        "(Например: Москва, Тверская улица, 15, офис 301)",
        reply_markup=cancel_inline_keyboard()  # ← ИСПРАВЛЕНО: инлайн-клавиатура
    )
    await state.set_state(AddressManagementStates.waiting_for_address)


@router.message(AddressManagementStates.waiting_for_address)
async def process_new_address(message: Message, state: FSMContext):
    """Обработка нового адреса и геокодирование"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="provider")
        return
    
    address = message.text.strip()
    
    # Геокодируем адрес
    coords = await geocode_address(address)
    if not coords:
        await message.answer(
            "❌ Не удалось определить координаты для этого адреса.\n"
            "Попробуйте указать более точный адрес:",
            reply_markup=provider_menu_keyboard()  # ← Обычная клавиатура для нового сообщения
        )
        return
    
    # Добавляем адрес (первый адрес автоматически становится основным)
    addresses = await get_provider_addresses(message.from_user.id)
    is_primary = len(addresses) == 0  # Первый адрес — основной
    
    await add_provider_address(
        provider_id=message.from_user.id,
        address=address,
        latitude=coords[0],
        longitude=coords[1],
        is_primary=is_primary
    )
    
    await message.answer(
        f"✅ Адрес добавлен!\n"
        f"Координаты: {coords[0]:.4f}, {coords[1]:.4f}\n"
        f"{'⭐ Это ваш основной адрес для поиска' if is_primary else 'Используйте меню «Адреса работы» чтобы назначить основным'}",
        reply_markup=provider_menu_keyboard()
    )
    await state.clear()


@router.callback_query(F.data.startswith("addr_action_"))
async def address_action_menu(callback: CallbackQuery, state: FSMContext):
    """Меню действий с адресом (сделать основным, удалить)"""
    await callback.answer()
    
    address_id = int(callback.data.split("_")[-1])
    
    # Сохраняем ID адреса в состоянии
    await state.update_data(current_address_id=address_id)
    
    await callback.message.edit_text(
        "Выберите действие с адресом:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Сделать основным", callback_data=f"addr_set_primary_{address_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"addr_delete_{address_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="addr_back")]
        ])
    )


@router.callback_query(F.data.startswith("addr_set_primary_"))
async def set_primary_address(callback: CallbackQuery, state: FSMContext):
    """Назначает адрес основным"""
    await callback.answer()
    
    address_id = int(callback.data.split("_")[-1])
    
    # Получаем текущие адреса для проверки
    addresses = await get_provider_addresses(callback.from_user.id)
    target_addr = next((a for a in addresses if a['id'] == address_id), None)
    
    if not target_addr:
        await callback.message.edit_text(
            "❌ Адрес не найден.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="addr_menu")]
            ])
        )
        return
    
    # Обновляем адрес (снимаем флаг с других, устанавливаем на этот)
    await add_provider_address(
        provider_id=callback.from_user.id,
        address=target_addr['address'],
        latitude=target_addr['latitude'],
        longitude=target_addr['longitude'],
        is_primary=True
    )
    
    await callback.message.edit_text(
        f"✅ Адрес '{target_addr['address'][:30]}...' назначен основным!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="addr_back")]
        ])
    )


@router.callback_query(F.data.startswith("addr_delete_"))
async def delete_address_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления адреса"""
    await callback.answer()
    
    address_id = int(callback.data.split("_")[-1])
    await state.update_data(address_to_delete=address_id)
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить этот адрес?\n"
        "Это может повлиять на поиск клиентами.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data="addr_confirm_delete")],
            [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="addr_back")]
        ])
    )


@router.callback_query(F.data == "addr_confirm_delete")
async def delete_address(callback: CallbackQuery, state: FSMContext):
    """Удаление адреса"""
    await callback.answer()
    
    data = await state.get_data()
    address_id = data.get('address_to_delete')
    
    if not address_id:
        await callback.message.edit_text(
            "❌ Ошибка: адрес не выбран.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="addr_menu")]
            ])
        )
        return
    
    try:
        await delete_provider_address(address_id, callback.from_user.id)
        await callback.message.edit_text(
            "✅ Адрес удалён!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="addr_menu")]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка удаления адреса: {e}")
        await callback.message.edit_text(
            "❌ Не удалось удалить адрес. Возможно, он используется в записях.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="addr_menu")]
            ])
        )


@router.callback_query(F.data == "addr_back")
async def back_to_addresses_list(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку адресов"""
    await callback.answer()
    
    addresses = await get_provider_addresses(callback.from_user.id)
    await callback.message.edit_text(
        "Ваши адреса работы:",
        reply_markup=get_addresses_keyboard(addresses)
    )


@router.callback_query(F.data == "addr_menu")
@router.callback_query(F.data == "cancel_action")  # ← Обработка отмены
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню мастера"""
    await callback.answer()
    await callback.message.edit_text(
        "Вы вернулись в меню мастера.",
        reply_markup=provider_menu_keyboard()  # ← Обычная клавиатура для нового сообщения
    )