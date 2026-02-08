"""
handlers/repeat_requests.py
===========================
Система запросов повторной записи для клиентов
Позволяет находить мастеров и отправлять запросы на повторную запись
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import RepeatRequestStates
from database import (
    get_client_providers_for_repeat,
    search_providers_for_repeat,
    create_repeat_request,
    get_pending_requests_for_client,
    add_request_message,
    get_request_messages,
    get_user_name
)
from keyboards import (
    repeat_request_menu_keyboard,
    search_type_keyboard,
    client_menu_keyboard,
    cancel_menu_keyboard,
    client_request_action_keyboard
)
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "Повторная запись")
async def start_repeat_request_menu(message: Message, state: FSMContext):
    """
    Главное меню запросов повторной записи для клиента
    """
    await message.answer(
        "Выберите действие:\n"
        "• 👤 Выбрать мастера из истории записей\n"
        "• 🔍 Найти мастера по услуге или имени\n"
        "• 📋 Посмотреть ваши активные запросы",
        reply_markup=repeat_request_menu_keyboard()
    )
    await state.set_state(RepeatRequestStates.choosing_provider)


@router.message(F.text == "👤 Выбрать из истории")
@router.message(RepeatRequestStates.choosing_provider, F.text == "👤 Выбрать из истории")
async def show_provider_history(message: Message, state: FSMContext):
    """
    Показывает список мастеров из истории клиента
    """
    providers = await get_client_providers_for_repeat(message.from_user.id)
    
    if not providers:
        await message.answer(
            "У вас нет истории записей к мастерам. Сначала запишитесь на услугу.",
            reply_markup=client_menu_keyboard()
        )
        return
    
    # Формируем пронумерованный список
    response = "📋 Выберите мастера из истории:\n\n"
    for i, provider in enumerate(providers, 1):
        response += (
            f"{i}. {provider['full_name']} (ID: {provider['user_code']})\n"
            f"   Услуги: {provider['services_list']}\n"
            f"   Записей: {provider['total_records']}\n\n"
        )
    
    response += "Введите номер мастера для отправки запроса:"
    
    # Сохраняем список для последующего выбора
    await state.update_data(providers=providers, search_results=None)
    await message.answer(response, reply_markup=cancel_menu_keyboard())
    await state.set_state(RepeatRequestStates.choosing_provider)


@router.message(F.text == "🔍 Найти мастера")
@router.message(RepeatRequestStates.choosing_search_type, F.text == "🔍 Найти мастера")
async def start_search(message: Message, state: FSMContext):
    """
    Начало поиска мастера — выбор типа поиска
    """
    await message.answer(
        "Выберите тип поиска:",
        reply_markup=search_type_keyboard()
    )
    await state.set_state(RepeatRequestStates.choosing_search_type)


@router.message(RepeatRequestStates.choosing_search_type, F.text.in_({"По услуге", "По имени мастера"}))
async def choose_search_type(message: Message, state: FSMContext):
    """
    Выбор типа поиска (по услуге или по имени)
    """
    search_type = 'service' if message.text == "По услуге" else 'name'
    search_label = "название услуги" if search_type == 'service' else "имя или фамилию мастера"
    
    await state.update_data(search_type=search_type)
    await message.answer(
        f"Введите {search_label} для поиска:",
        reply_markup=cancel_menu_keyboard()
    )
    await state.set_state(RepeatRequestStates.entering_search_query)


@router.message(RepeatRequestStates.entering_search_query)
async def process_search_query(message: Message, state: FSMContext):
    """
    Обработка поискового запроса и показ результатов
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    query = message.text.strip()
    data = await state.get_data()
    search_type = data.get('search_type', 'service')
    
    # Выполняем поиск
    results = await search_providers_for_repeat(
        message.from_user.id,
        query,
        search_type
    )
    
    if not results:
        await message.answer(
            f"Не найдено мастеров по запросу '{query}'.\nПопробуйте другой запрос:",
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Формируем пронумерованный список результатов
    response = f"🔍 Найдено {len(results)} мастеров:\n\n"
    for i, provider in enumerate(results, 1):
        response += (
            f"{i}. {provider['full_name']} (ID: {provider['user_code']})\n"
            f"   Услуги: {provider['services_list']}\n"
            f"   Записей: {provider['total_records']}\n\n"
        )
    
    response += "Введите номер мастера для отправки запроса:"
    
    # Сохраняем результаты поиска
    await state.update_data(search_results=results, providers=None)
    await message.answer(response, reply_markup=cancel_menu_keyboard())
    await state.set_state(RepeatRequestStates.choosing_from_search)


@router.message(RepeatRequestStates.choosing_provider)
@router.message(RepeatRequestStates.choosing_from_search)
async def choose_provider(message: Message, state: FSMContext):
    """
    Выбор мастера из списка (история или поиск) и начало написания сообщения
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    try:
        # Определяем источник списка (история или поиск)
        data = await state.get_data()
        providers = data.get('providers') or data.get('search_results')
        
        if not providers:
            await message.answer("Ошибка: список мастеров пуст. Начните заново.", reply_markup=client_menu_keyboard())
            await state.clear()
            return
        
        # Преобразуем ввод в индекс
        provider_num = int(message.text.strip()) - 1
        
        # Проверяем корректность индекса
        if provider_num < 0 or provider_num >= len(providers):
            raise ValueError
        
        # Получаем выбранного мастера
        selected_provider = providers[provider_num]
        
        # Сохраняем данные мастера
        await state.update_data(
            selected_provider_id=selected_provider['provider_id'],
            selected_provider_name=selected_provider['full_name'],
            selected_service_name=selected_provider['services_list'].split(',')[0].strip() if selected_provider['services_list'] else None
        )
        
        # Запрашиваем сообщение для мастера
        await message.answer(
            f"Вы выбрали мастера: {selected_provider['full_name']} (ID: {selected_provider['user_code']})\n\n"
            "Напишите сообщение мастеру (например, предложите дату и время):",
            reply_markup=cancel_menu_keyboard()
        )
        await state.set_state(RepeatRequestStates.writing_message)
    
    except (ValueError, IndexError):
        await message.answer(
            f"Неверный номер. Введите число от 1 до {len(providers)}:",
            reply_markup=cancel_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка выбора мастера: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=client_menu_keyboard())
        await state.clear()


@router.message(RepeatRequestStates.writing_message)
async def send_request_message(message: Message, state: FSMContext):
    """
    Отправка первого сообщения в запросе на повторную запись
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    # Получаем данные о мастере
    data = await state.get_data()
    provider_id = data['selected_provider_id']
    service_name = data.get('selected_service_name')
    
    # Создаём запрос в БД
    request_id = await create_repeat_request(
        message.from_user.id,
        provider_id,
        service_name
    )
    
    # Сохраняем сообщение
    await add_request_message(
        request_id,
        sender_role='client',
        sender_id=message.from_user.id,
        message_text=message.text
    )
    
    # Подтверждение клиенту
    await message.answer(
        f"✅ Запрос отправлен мастеру {data['selected_provider_name']}!\n"
        "Вы получите уведомление, когда мастер ответит.",
        reply_markup=client_menu_keyboard()
    )
    
    # Очищаем состояние
    await state.clear()


@router.message(F.text == "📋 Мои запросы")
async def show_client_requests(message: Message, state: FSMContext):
    """
    Показывает список активных запросов клиента
    """
    requests = await get_pending_requests_for_client(message.from_user.id)
    
    if not requests:
        await message.answer(
            "У вас нет активных запросов.",
            reply_markup=repeat_request_menu_keyboard()
        )
        return
    
    # Формируем пронумерованный список запросов
    response = "📋 Ваши запросы:\n\n"
    for i, req in enumerate(requests, 1):
        response += (
            f"{i}. {req['provider_name']} (ID: {req['provider_code']})\n"
            f"   Услуга: {req['service_name']}\n"
            f"   Статус: {req['status']}\n"
            f"   Сообщений: {req['message_count']}\n"
            f"   Отправлено: {req['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    response += "Введите номер запроса для просмотра диалога:"
    
    # Сохраняем список запросов
    await state.update_data(client_requests=requests)
    await message.answer(response, reply_markup=cancel_menu_keyboard())
    await state.set_state(RepeatRequestStates.chatting)


@router.message(RepeatRequestStates.chatting)
async def view_request_dialog(message: Message, state: FSMContext, bot):
    """
    Просмотр диалога запроса и отправка ответа
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="client")
        return
    
    try:
        # Получаем список запросов
        data = await state.get_data()
        requests = data.get('client_requests', [])
        
        if not requests:
            await message.answer("Ошибка: список запросов пуст.", reply_markup=client_menu_keyboard())
            await state.clear()
            return
        
        # Преобразуем ввод в индекс
        req_num = int(message.text.strip()) - 1
        
        # Проверяем корректность индекса
        if req_num < 0 or req_num >= len(requests):
            raise ValueError
        
        # Получаем выбранный запрос
        selected_request = requests[req_num]
        request_id = selected_request['request_id']
        
        # Получаем все сообщения в диалоге
        messages = await get_request_messages(request_id)
        
        # Формируем историю диалога
        dialog_text = f"💬 Диалог с {selected_request['provider_name']}:\n\n"
        for msg in messages:
            sender_prefix = "👤 Вы:" if msg['sender_role'] == 'client' else f"👑 {msg['sender_name']}:"
            time_str = msg['sent_at'].strftime('%H:%M')
            dialog_text += f"[{time_str}] {sender_prefix}\n{msg['message_text']}\n\n"
        
        # Отправляем историю
        await message.answer(
            dialog_text.strip(),
            reply_markup=client_request_action_keyboard()
        )
        
        # Сохраняем ID запроса для ответа
        await state.update_data(current_request_id=request_id)
        await state.set_state(RepeatRequestStates.writing_message)
    
    except (ValueError, IndexError):
        await message.answer(
            f"Неверный номер. Введите число от 1 до {len(requests)}:",
            reply_markup=cancel_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка просмотра диалога: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=client_menu_keyboard())
        await state.clear()