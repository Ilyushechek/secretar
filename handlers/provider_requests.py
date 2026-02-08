"""
handlers/provider_requests.py
=============================
Система запросов повторной записи для мастеров
Позволяет просматривать и отвечать на запросы клиентов
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import RepeatRequestStates
from database import (
    get_pending_requests_for_provider,
    get_request_messages,
    add_request_message,
    accept_repeat_request,
    reject_repeat_request
)
from keyboards import (
    provider_requests_menu_keyboard,
    request_action_keyboard,
    provider_menu_keyboard,
    cancel_menu_keyboard
)
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "📥 Запросы")
async def show_provider_requests_menu(message: Message, state: FSMContext):
    """
    Главное меню запросов для мастера
    """
    await message.answer(
        "📥 Запросы на повторную запись:\n"
        "• Новые запросы — от клиентов, ожидающих ответа\n"
        "• Мои диалоги — активные переписки с клиентами",
        reply_markup=provider_requests_menu_keyboard()
    )
    await state.set_state(RepeatRequestStates.viewing_requests)


@router.message(F.text == "📥 Новые запросы")
@router.message(RepeatRequestStates.viewing_requests, F.text == "📥 Новые запросы")
async def show_pending_requests(message: Message, state: FSMContext):
    """
    Показывает список непрочитанных запросов для мастера
    """
    requests = await get_pending_requests_for_provider(message.from_user.id)
    
    if not requests:
        await message.answer(
            "У вас нет новых запросов.",
            reply_markup=provider_requests_menu_keyboard()
        )
        return
    
    # Формируем пронумерованный список запросов
    response = "📥 Новые запросы:\n\n"
    for i, req in enumerate(requests, 1):
        response += (
            f"{i}. {req['client_name']} (ID: {req['client_code']})\n"
            f"   Услуга: {req['service_name']}\n"
            f"   Сообщений: {req['message_count']}\n"
            f"   Отправлено: {req['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    response += "Введите номер запроса для просмотра:"
    
    # Сохраняем список запросов
    await state.update_data(provider_requests=requests)
    await message.answer(response, reply_markup=cancel_menu_keyboard())
    await state.set_state(RepeatRequestStates.chatting)


@router.message(RepeatRequestStates.chatting)
async def view_provider_request_dialog(message: Message, state: FSMContext, bot):
    """
    Просмотр диалога запроса и выбор действия
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    try:
        # Получаем список запросов
        data = await state.get_data()
        requests = data.get('provider_requests', [])
        
        if not requests:
            await message.answer("Ошибка: список запросов пуст.", reply_markup=provider_menu_keyboard())
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
        
        # Сохраняем данные запроса
        await state.update_data(
            current_request_id=request_id,
            current_client_id=selected_request['client_id'],
            current_client_name=selected_request['client_name']
        )
        
        # Получаем все сообщения в диалоге
        messages = await get_request_messages(request_id)
        
        # Формируем историю диалога
        dialog_text = f"💬 Запрос от {selected_request['client_name']}:\n\n"
        for msg in messages:
            sender_prefix = f"👤 {msg['sender_name']}:" if msg['sender_role'] == 'client' else "👑 Вы:"
            time_str = msg['sent_at'].strftime('%H:%M')
            dialog_text += f"[{time_str}] {sender_prefix}\n{msg['message_text']}\n\n"
        
        # Отправляем историю + клавиатура действий
        await message.answer(
            dialog_text.strip(),
            reply_markup=request_action_keyboard()
        )
    
    except (ValueError, IndexError):
        await message.answer(
            f"Неверный номер. Введите число от 1 до {len(requests)}:",
            reply_markup=cancel_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка просмотра диалога: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.", reply_markup=provider_menu_keyboard())
        await state.clear()


@router.message(F.text == "✅ Принять")
async def accept_request(message: Message, state: FSMContext):
    """
    Принятие запроса на повторную запись
    """
    data = await state.get_data()
    request_id = data.get('current_request_id')
    
    if not request_id:
        await message.answer("Ошибка: запрос не выбран.", reply_markup=provider_menu_keyboard())
        return
    
    # Принимаем запрос
    success = await accept_repeat_request(request_id, message.from_user.id)
    
    if success:
        await message.answer(
            f"✅ Запрос принят!\n"
            "Клиент получит уведомление. Вы можете продолжить диалог или создать запись.",
            reply_markup=request_action_keyboard()
        )
    else:
        await message.answer(
            "❌ Не удалось принять запрос. Возможно, он уже обработан.",
            reply_markup=provider_menu_keyboard()
        )


@router.message(F.text == "❌ Отклонить")
async def reject_request(message: Message, state: FSMContext):
    """
    Отклонение запроса на повторную запись
    """
    data = await state.get_data()
    request_id = data.get('current_request_id')
    
    if not request_id:
        await message.answer("Ошибка: запрос не выбран.", reply_markup=provider_menu_keyboard())
        return
    
    # Отклоняем запрос
    success = await reject_repeat_request(request_id, message.from_user.id)
    
    if success:
        await message.answer(
            "❌ Запрос отклонён.\nКлиент получит уведомление.",
            reply_markup=provider_requests_menu_keyboard()
        )
        await state.clear()
    else:
        await message.answer(
            "❌ Не удалось отклонить запрос. Возможно, он уже обработан.",
            reply_markup=provider_menu_keyboard()
        )


@router.message(F.text == "✏️ Ответить")
async def start_reply(message: Message, state: FSMContext):
    """
    Начало написания ответа клиенту
    """
    data = await state.get_data()
    request_id = data.get('current_request_id')
    client_name = data.get('current_client_name')
    
    if not request_id:
        await message.answer("Ошибка: запрос не выбран.", reply_markup=provider_menu_keyboard())
        return
    
    await message.answer(
        f"Напишите ответ для {client_name}:\n"
        "(Можно отправить текст или фото)",
        reply_markup=cancel_menu_keyboard()
    )
    await state.set_state(RepeatRequestStates.writing_message)


@router.message(RepeatRequestStates.writing_message)
async def send_reply(message: Message, state: FSMContext, bot):
    """
    Отправка ответа клиенту в диалоге запроса
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    data = await state.get_data()
    request_id = data.get('current_request_id')
    
    if not request_id:
        await message.answer("Ошибка: запрос не выбран.", reply_markup=provider_menu_keyboard())
        return
    
    # Обрабатываем текст или фото
    if message.text:
        await add_request_message(
            request_id,
            sender_role='provider',
            sender_id=message.from_user.id,
            message_text=message.text
        )
        await message.answer("✅ Ответ отправлен!", reply_markup=request_action_keyboard())
    
    elif message.photo:
        photo = message.photo[-1]  # Самое большое разрешение
        caption = message.caption or "Фотография"
        
        await add_request_message(
            request_id,
            sender_role='provider',
            sender_id=message.from_user.id,
            message_text=caption,
            photo_file_id=photo.file_id
        )
        
        # Отправляем фото клиенту (опционально)
        client_id = data.get('current_client_id')
        if client_id:
            try:
                await bot.send_photo(
                    client_id,
                    photo=photo.file_id,
                    caption=f"👑 Мастер отправил фото:\n{caption}"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить фото клиенту: {e}")
        
        await message.answer("✅ Фото и ответ отправлены!", reply_markup=request_action_keyboard())
    
    else:
        await message.answer("Поддерживаются только текст и фото. Попробуйте снова:")


@router.message(F.text == "📄 Создать запись")
async def create_record_from_request(message: Message, state: FSMContext):
    """
    Создание записи на услугу из запроса (автоматическое заполнение ID клиента)
    """
    data = await state.get_data()
    client_id = data.get('current_client_id')
    client_name = data.get('current_client_name')
    
    if not client_id:
        await message.answer("Ошибка: клиент не выбран.", reply_markup=provider_menu_keyboard())
        return
    
    # Автоматически заполняем ID клиента в состоянии создания записи
    await state.update_data(
        client_telegram_id=client_id,
        from_chat=True,
        user_role="provider"
    )
    
    # Переходим к созданию записи
    from FSMstates import ServiceRecordStates
    await state.set_state(ServiceRecordStates.waiting_for_service_name)
    
    await message.answer(
        f"Создание записи для клиента: {client_name}\n"
        "Введите название услуги:",
        reply_markup=cancel_menu_keyboard()
    )