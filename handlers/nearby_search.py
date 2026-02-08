"""
handlers/nearby_search.py
=========================
Поиск ближайших мастеров по адресу и услуге
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import NearbySearchStates
from database import search_nearby_providers, geocode_address
from keyboards import client_menu_keyboard, cancel_menu_keyboard
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "🔍 Найти мастера рядом")
async def start_nearby_search(message: Message, state: FSMContext):
    """
    Начало поиска ближайших мастеров
    
    Запрашивает у клиента адрес для поиска
    """
    await message.answer(
        "📍 Укажите ваш адрес для поиска ближайших мастеров:\n"
        "(Например: Москва, Тверская улица, 1)",
        reply_markup=cancel_menu_keyboard()
    )
    await state.set_state(NearbySearchStates.waiting_for_address)


@router.message(NearbySearchStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """
    Обработка адреса клиента
    
    Проверяет валидность адреса через геокодирование
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    address = message.text.strip()
    
    # Проверяем адрес через геокодирование
    coords = await geocode_address(address)
    if not coords:
        await message.answer(
            "❌ Не удалось определить координаты по этому адресу.\n"
            "Попробуйте указать более точный адрес (город, улица, дом):",
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Сохраняем адрес и запрашиваем услугу
    await state.update_data(client_address=address, client_coords=coords)
    await message.answer(
        "🔧 Какую услугу вы ищете?\n"
        "(Например: маникюр, ремонт сантехники, массаж)",
        reply_markup=cancel_menu_keyboard()
    )
    await state.set_state(NearbySearchStates.waiting_for_service)


@router.message(NearbySearchStates.waiting_for_service)
async def process_service_and_search(message: Message, state: FSMContext):
    """
    Обработка названия услуги и выполнение поиска
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    service_query = message.text.strip()
    data = await state.get_data()
    client_address = data['client_address']
    
    try:
        # Выполняем поиск мастеров
        providers = await search_nearby_providers(client_address, service_query, limit=10)
        
        if not providers:
            await message.answer(
                f"❌ Не найдено мастеров с услугой '{service_query}' в вашем районе.\n"
                "Попробуйте указать услугу другими словами или расширить поиск.",
                reply_markup=client_menu_keyboard()
            )
            await state.clear()
            return
        
        # Формируем результат поиска
        response = f"✅ Найдено {len(providers)} мастеров поблизости:\n\n"
        for i, provider in enumerate(providers, 1):
            distance = provider['distance_km']
            response += (
                f"{i}. {provider['full_name']} (ID: {provider['user_code']})\n"
                f"   📍 {provider['address']}\n"
                f"   📏 {distance} км от вас\n"
                f"   🔧 {provider['service_name']}\n"
            )
            if provider.get('description'):
                response += f"   ℹ️ {provider['description'][:50]}...\n"
            response += "\n"
        
        response += (
            "💡 Чтобы записаться к мастеру:\n"
            "1. Запомните его ID (например, 000123)\n"
            "2. Нажмите «Связаться с мастером»\n"
            "3. Введите этот ID"
        )
        
        await message.answer(response, reply_markup=client_menu_keyboard())
        await state.clear()
    
    except Exception as e:
        logger.error(f"Ошибка поиска мастеров: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске. Попробуйте позже.",
            reply_markup=client_menu_keyboard()
        )
        await state.clear()