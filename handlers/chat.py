"""
handlers/chat.py
================
Обработчик переписки между клиентом и мастером.
Поддерживает создание чата, пересылку сообщений и завершение чата.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
import logging
from FSMstates import ClientChatStates, ProviderChatStates
from database import (
    get_user_telegram_id_by_code,
    create_chat,
    get_active_chat_by_client,
    get_active_chat_by_provider,
    close_chat,
    get_user_name,
    get_db_connection
)
from keyboards import (
    client_menu_keyboard,
    provider_menu_keyboard,
    client_chat_active_keyboard,
    provider_chat_active_keyboard,
    chat_request_inline,
    create_record_after_chat_inline
)
from handlers.logout import return_to_role_menu  # ← ПРАВИЛЬНЫЙ ИМПОРТ ФУНКЦИИ

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки чата
router = Router()


async def close_chat_and_offer_record(chat_id: int, provider_id: int, client_id: int, bot):
    """
    Завершает чат и предлагает мастеру создать запись на услугу
    
    УВЕДОМЛЕНИЯ: клиент получает уведомление ТОЛЬКО при создании записи (не здесь)
    """
    # Завершаем чат в БД
    await close_chat(chat_id)
    
    try:
        # Получаем имя клиента для персонализации сообщения
        client_info = await get_user_name(client_id)
        client_display = (
            f"{client_info['first_name'] or ''} {client_info['last_name'] or ''}".strip() 
            or "Клиент"
        )
        
        # Отправляем мастеру предложение создать запись (реальное время, без сохранения)
        await bot.send_message(
            provider_id,
            f"Чат с {client_display} завершён.\n"
            "Хотите создать запись на услугу для этого клиента?",
            reply_markup=create_record_after_chat_inline(chat_id)
        )
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logger.error(f"Ошибка отправки предложения о записи: {e}")
    
    # Клиенту отправляем уведомление о завершении чата (реальное время)
    try:
        await bot.send_message(
            client_id, 
            "Чат с мастером завершён.", 
            reply_markup=client_menu_keyboard()
        )
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logger.error(f"Ошибка отправки клиенту: {e}")


@router.message(F.text == "Связаться с мастером")
async def start_contact(message: Message, state: FSMContext):
    """
    Начало процесса связи с мастером (для клиента).
    
    Проверяет наличие активного чата.
    Запрашивает 6-значный ID мастера.
    """
    # Проверяем наличие активного чата
    active_chat = await get_active_chat_by_client(message.from_user.id)
    if active_chat:
        await message.answer("У вас уже есть активный чат с мастером.")
        return
    
    # Запрашиваем ID мастера
    await message.answer("Введите 6-значный ID мастера:")
    await state.set_state(ClientChatStates.waiting_for_provider_id)


@router.message(ClientChatStates.waiting_for_provider_id)
async def process_provider_id(message: Message, state: FSMContext, bot):
    """
    Обработка ID мастера от клиента.
    
    Проверяет формат, существование мастера и создаёт запрос на чат.
    """
    # Получаем и проверяем формат ID
    user_code = message.text.strip()
    if not user_code.isdigit() or len(user_code) != 6:
        await message.answer("Неверный формат ID. Введите 6 цифр:")
        return
    
    # Получаем telegram_id мастера по коду
    provider_telegram_id = await get_user_telegram_id_by_code(user_code)
    if not provider_telegram_id:
        await message.answer("Мастер с таким ID не найден. Попробуйте снова:")
        return
    
    # ⚠️ ОТЛАДКА: разрешаем связь с самим собой (закомментируйте для продакшена)
    # if provider_telegram_id == message.from_user.id:
    #     await message.answer("Вы не можете связаться сами с собой.")
    #     return
    
    # Создаём чат в БД
    chat_id = await create_chat(message.from_user.id, provider_telegram_id)
    
    try:
        # Отправляем мастеру запрос на чат
        await bot.send_message(
            provider_telegram_id,
            f"🔔 Запрос от клиента (ID: {user_code})\nПринять?",
            reply_markup=chat_request_inline(chat_id)
        )
        await message.answer("Запрос отправлен мастеру. Ожидайте ответа.")
    except TelegramForbiddenError:
        # Мастер заблокировал бота
        await message.answer("Не удалось отправить запрос: мастер заблокировал бота.")
        await close_chat(chat_id)  # Закрываем чат
        return
    
    # Сохраняем данные чата в состоянии клиента
    await state.set_state(ClientChatStates.in_chat)
    await state.update_data(
        chat_id=chat_id, 
        partner_id=provider_telegram_id,
        user_role="client"
    )
    
    # Показываем клавиатуру активного чата
    await message.answer(
        "Чат начат. Нажмите «Завершить чат», чтобы остановить общение.", 
        reply_markup=client_chat_active_keyboard()
    )


@router.callback_query(F.data.startswith("accept_chat_"))
async def accept_chat(callback: CallbackQuery, state: FSMContext, bot):
    """
    Обработчик принятия запроса на чат (мастером).
    
    Активирует чат и уведомляет клиента.
    """
    # Извлекаем ID чата из callback_data
    chat_id = int(callback.data.split("_")[-1])
    
    # Проверяем, что чат активен и принадлежит мастеру
    active_chat = await get_active_chat_by_provider(callback.from_user.id)
    if not active_chat or active_chat["id"] != chat_id:
        await callback.answer("Чат уже закрыт или не найден.", show_alert=True)
        return
    
    # Получаем ID клиента
    client_id = active_chat["client_telegram_id"]
    
    try:
        # Уведомляем клиента о принятии запроса
        await bot.send_message(
            client_id,
            "✅ Мастер принял ваш запрос! Теперь вы можете писать друг другу."
        )
        
        # Уведомляем мастера об активации чата
        await bot.send_message(
            callback.from_user.id,
            "✅ Вы приняли запрос! Теперь вы можете писать клиенту.\n"
            "Нажмите «Завершить чат», чтобы остановить общение.",
            reply_markup=provider_chat_active_keyboard()
        )
    except TelegramForbiddenError:
        # Клиент заблокировал бота
        await callback.answer("Клиент заблокировал бота.", show_alert=True)
        await close_chat(chat_id)
        return
    
    # Сохраняем данные чата в состоянии мастера
    await state.set_state(ProviderChatStates.in_chat)
    await state.update_data(
        chat_id=chat_id, 
        partner_id=client_id,
        user_role="provider"
    )
    
    # Подтверждаем нажатие кнопки
    await callback.answer()
    await callback.message.edit_text("Чат активен.")


@router.callback_query(F.data.startswith("reject_chat_"))
async def reject_chat(callback: CallbackQuery, bot):
    """
    Обработчик отклонения запроса на чат (мастером).
    
    Завершает чат и уведомляет клиента.
    """
    # Извлекаем ID чата
    chat_id = int(callback.data.split("_")[-1])
    
    # Получаем данные чата
    active_chat = await get_active_chat_by_provider(callback.from_user.id)
    if active_chat and active_chat["id"] == chat_id:
        client_id = active_chat["client_telegram_id"]
        try:
            # Уведомляем клиента об отклонении
            await bot.send_message(
                client_id, 
                "❌ Мастер отклонил ваш запрос.", 
                reply_markup=client_menu_keyboard()
            )
        except TelegramForbiddenError:
            pass
        # Завершаем чат в БД
        await close_chat(chat_id)
    
    # Подтверждаем нажатие кнопки
    await callback.answer("Запрос отклонён.", show_alert=True)
    await callback.message.edit_text("Запрос отклонён.")


@router.callback_query(F.data.startswith("create_record_no_"))
async def handle_create_record_no(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик отказа от создания записи после чата.
    
    Возвращает мастера в меню.
    """
    await callback.answer()
    await callback.message.edit_text(
        "Вы вернулись в меню.", 
        reply_markup=provider_menu_keyboard()
    )
    await state.update_data(user_role="provider")


@router.callback_query(F.data.startswith("create_record_yes_"))
async def handle_create_record_yes(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик согласия на создание записи после чата.
    
    Получает данные клиента из БД и начинает процесс создания записи.
    """
    # Извлекаем ID чата
    chat_id = int(callback.data.split("_")[-1])
    
    # Получаем ID клиента из БД по ID чата
    conn = await get_db_connection()
    try:
        row = await conn.fetchrow(
            "SELECT client_telegram_id FROM chats WHERE id = $1", 
            chat_id
        )
        if not row:
            await callback.answer("Чат не найден.", show_alert=True)
            return
        client_id = row["client_telegram_id"]
    finally:
        await conn.close()
    
    # Подтверждаем нажатие кнопки
    await callback.answer()
    
    # Редактируем сообщение на запрос названия услуги
    await callback.message.edit_text("Введите название услуги:")
    
    # Сохраняем ID клиента и начинаем создание записи
    await state.update_data(
        client_telegram_id=client_id, 
        from_chat=True,
        user_role="provider"
    )
    from FSMstates import ServiceRecordStates
    await state.set_state(ServiceRecordStates.waiting_for_service_name)


@router.message(ClientChatStates.in_chat, F.text == "Завершить чат")
async def client_end_chat(message: Message, state: FSMContext, bot):
    """
    Завершение чата клиентом.
    
    Закрывает чат и предлагает мастеру создать запись.
    """
    # Получаем данные чата из состояния
    data = await state.get_data()
    chat_id = data.get("chat_id")
    partner_id = data.get("partner_id")
    
    # Завершаем чат и предлагаем запись мастеру
    if chat_id and partner_id:
        await close_chat_and_offer_record(chat_id, partner_id, message.from_user.id, bot)
    
    # Возвращаем клиента в меню
    await message.answer("Вы вышли из чата.", reply_markup=client_menu_keyboard())
    await state.clear()


@router.message(ProviderChatStates.in_chat, F.text == "Завершить чат")
async def provider_end_chat(message: Message, state: FSMContext, bot):
    """
    Завершение чата мастером.
    
    Закрывает чат и предлагает создать запись на услугу.
    """
    # Получаем данные чата из состояния
    data = await state.get_data()
    chat_id = data.get("chat_id")
    partner_id = data.get("partner_id")
    
    # Завершаем чат и предлагаем запись
    if chat_id and partner_id:
        await close_chat_and_offer_record(chat_id, message.from_user.id, partner_id, bot)
    
    # Возвращаем мастера в меню
    await message.answer("Вы вышли из чата.", reply_markup=provider_menu_keyboard())
    await state.clear()


@router.message(ClientChatStates.in_chat)
async def forward_from_client(message: Message, state: FSMContext, bot):
    """
    Пересылка сообщений от клиента мастеру.
    
    Добавляет префикс "Сообщение от клиента:" для идентификации.
    """
    # Получаем данные чата
    data = await state.get_data()
    partner_id = data.get("partner_id")
    
    # Проверяем корректность состояния
    if not partner_id:
        await message.answer("Ошибка сессии.", reply_markup=client_menu_keyboard())
        await state.clear()
        return
    
    try:
        # Пересылаем сообщение мастеру с префиксом
        await bot.send_message(
            partner_id, 
            f"Сообщение от клиента:\n\n{message.text}"
        )
    except TelegramForbiddenError:
        # Мастер заблокировал бота — завершаем чат
        chat_id = data.get("chat_id")
        if chat_id:
            await close_chat_and_offer_record(
                chat_id, 
                partner_id, 
                message.from_user.id, 
                bot
            )
        await message.answer(
            "Мастер заблокировал бота. Чат завершён.", 
            reply_markup=client_menu_keyboard()
        )
        await state.clear()


@router.message(ProviderChatStates.in_chat)
async def forward_from_provider(message: Message, state: FSMContext, bot):
    """
    Пересылка сообщений от мастера клиенту.
    
    Добавляет префикс "Сообщение от мастера:" для идентификации.
    """
    # Получаем данные чата
    data = await state.get_data()
    partner_id = data.get("partner_id")
    
    # Проверяем корректность состояния
    if not partner_id:
        await message.answer("Ошибка сессии.", reply_markup=provider_menu_keyboard())
        await state.clear()
        return
    
    try:
        # Пересылаем сообщение клиенту с префиксом
        await bot.send_message(
            partner_id, 
            f"Сообщение от мастера:\n\n{message.text}"
        )
    except TelegramForbiddenError:
        # Клиент заблокировал бота — завершаем чат
        chat_id = data.get("chat_id")
        if chat_id:
            await close_chat_and_offer_record(
                chat_id, 
                message.from_user.id, 
                partner_id, 
                bot
            )
        await message.answer(
            "Клиент заблокировал бота. Чат завершён.", 
            reply_markup=provider_menu_keyboard()
        )
        await state.clear()