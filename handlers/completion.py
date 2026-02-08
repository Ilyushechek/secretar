"""
handlers/completion.py
======================
Обработчик завершения услуги после её выполнения
Позволяет мастеру указать длительность, оценку, комментарии и добавить фотографии
"""

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError
import logging
from FSMstates import CompletionStates, PhotoStates
from database import (
    get_active_records_for_provider,
    complete_service,
    get_user_name,
    get_client_from_record,
    create_notification,
    add_service_photo
)
from keyboards import (
    yes_no_keyboard,
    cancel_menu_keyboard,
    provider_menu_keyboard
)
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки завершения услуг
router = Router()


@router.message(F.text == "Завершить услугу")
async def start_completion(message: Message, state: FSMContext):
    """
    Начало процесса завершения услуги
    
    Показывает список активных записей для выбора
    
    Args:
        message (Message): Входящее сообщение
        state (FSMContext): Контекст состояния
    """
    # Получаем активные записи мастера
    records = await get_active_records_for_provider(message.from_user.id)
    
    # Проверяем наличие записей
    if not records:
        await message.answer("У вас нет активных записей для завершения.")
        return
    
    # Формируем сообщение со списком записей
    response = "Выберите запись для завершения:\n\n"
    for i, record in enumerate(records, 1):
        # Получаем имя клиента для отображения
        client_info = await get_user_name(record['client_telegram_id'])
        client_name = (
            f"{client_info['first_name'] or ''} {client_info['last_name'] or ''}".strip() 
            or "Клиент"
        )
        response += (
            f"{i}. {record['service_name']} — "
            f"{record['service_date']} {record['service_time']}\n"
            f"   Клиент: {client_name}\n\n"
        )
    
    # Сохраняем список записей в состоянии
    await state.update_data(records=records)
    
    # Запрашиваем номер записи
    await message.answer(
        response + "Введите номер записи:", 
        reply_markup=cancel_menu_keyboard()
    )
    
    # Устанавливаем состояние выбора записи
    await state.set_state(CompletionStates.waiting_for_record_id)


@router.message(CompletionStates.waiting_for_record_id)
async def process_record_id(message: Message, state: FSMContext):
    """
    Обработка выбора записи для завершения
    
    Проверяет корректность номера и сохраняет выбранный ID
    
    Args:
        message (Message): Сообщение с номером записи
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    try:
        # Преобразуем ввод в индекс (нумерация с 1)
        record_num = int(message.text.strip()) - 1
        
        # Получаем данные из состояния
        data = await state.get_data()
        records = data['records']
        
        # Проверяем корректность индекса
        if record_num < 0 or record_num >= len(records):
            raise ValueError
        
        # Сохраняем выбранный ID записи и индекс
        record_id = records[record_num]['id']
        await state.update_data(
            record_id=record_id, 
            record_index=record_num
        )
        
        # Запрашиваем длительность услуги
        await message.answer(
            "Сколько минут длилась услуга?", 
            reply_markup=cancel_menu_keyboard()
        )
        
        # Устанавливаем состояние ввода длительности
        await state.set_state(CompletionStates.waiting_for_duration)
    
    except Exception as e:
        logger.error(f"Ошибка выбора записи: {e}")
        await message.answer(
            f"Неверный номер. Введите число от 1 до {len(records)}:", 
            reply_markup=cancel_menu_keyboard()
        )


@router.message(CompletionStates.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    """
    Обработка ввода длительности услуги
    
    Проверяет, что введено положительное число
    
    Args:
        message (Message): Сообщение с длительностью
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    try:
        # Преобразуем ввод в число
        duration = int(message.text.strip())
        
        # Проверяем положительность
        if duration <= 0:
            raise ValueError
        
        # Сохраняем длительность
        await state.update_data(duration=duration)
        
        # Запрашиваем оценку качества
        await message.answer(
            "Хорошо ли прошла услуга?", 
            reply_markup=yes_no_keyboard()
        )
        
        # Устанавливаем состояние ввода оценки
        await state.set_state(CompletionStates.waiting_for_rating)
    
    except:
        await message.answer("Введите положительное число минут:")


@router.message(CompletionStates.waiting_for_rating)
async def process_rating(message: Message, state: FSMContext):
    """
    Обработка оценки качества услуги
    
    Преобразует ответ "Да/Нет" в булево значение
    
    Args:
        message (Message): Сообщение с оценкой
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Преобразуем ответ в булево значение
    rating = message.text.strip() == "✅ Да"
    
    # Сохраняем оценку
    await state.update_data(rating=rating)
    
    # Запрашиваем комментарии
    await message.answer(
        "Добавьте комментарии (или '-' если нет):", 
        reply_markup=cancel_menu_keyboard()
    )
    
    # Устанавливаем состояние ввода комментариев
    await state.set_state(CompletionStates.waiting_for_notes)


@router.message(CompletionStates.waiting_for_notes)
async def process_notes_and_complete(message: Message, state: FSMContext, bot):
    """
    Обработка комментариев и завершение услуги
    
    После успешного завершения предлагает мастеру добавить фотографии результата.
    Сохраняет результат в БД и уведомляет клиента.
    
    Args:
        message (Message): Сообщение с комментариями
        state (FSMContext): Контекст состояния
        bot (Bot): Экземпляр бота для отправки сообщений
    """
    # Проверка отмены действия (нажатие "В меню")
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Обрабатываем комментарии
    notes = message.text.strip() if message.text.strip() != '-' else ''
    
    # Получаем данные из состояния
    data = await state.get_data()
    
    # Завершаем услугу в БД
    success = await complete_service(
        record_id=data['record_id'],
        provider_id=message.from_user.id,
        duration_minutes=data['duration'],
        rating=data['rating'],
        notes=notes
    )
    
    if success:
        # Уведомляем клиента о завершении услуги
        client_id = await get_client_from_record(data['record_id'])
        if client_id:
            records = data.get('records', [])
            record_index = data.get('record_index', 0)
            if record_index < len(records):
                service_name = records[record_index]['service_name']
                status_text = "успешно завершена ✅" if data['rating'] else "завершена ⚠️"
                try:
                    await create_notification(
                        telegram_id=client_id,
                        role="client",
                        message_text=(
                            f"🔔 Ваша запись '{service_name}' {status_text}.\n"
                            f"Длительность: {data['duration']} мин\n"
                            f"Комментарии: {notes}"
                        )
                    )
                except Exception as e:
                    logger.error(f"Ошибка создания уведомления клиенту: {e}")
        
        # Формируем статус для мастера
        status = "успешно завершена" if data['rating'] else "завершена с замечаниями"
        
        # Подтверждаем завершение и предлагаем добавить фото
        await message.answer(
            f"✅ Услуга {status}!\n"
            f"Длительность: {data['duration']} мин\n"
            f"Комментарии: {notes}\n\n"
            f"Хотите добавить фотографии результата?",
            reply_markup=yes_no_keyboard()
        )
        
        # Сохраняем ID записи для последующего добавления фото
        await state.update_data(record_id=data['record_id'])
        await state.set_state(PhotoStates.waiting_for_photos)
        
    else:
        # Ошибка завершения
        await message.answer(
            "❌ Не удалось завершить услугу. "
            "Возможно, запись уже отменена или завершена."
        )
        
        # Возвращаемся в меню мастера
        await state.clear()
        await return_to_role_menu(message, state, role="provider")


@router.message(PhotoStates.waiting_for_photos)
async def ask_for_photos(message: Message, state: FSMContext):
    """
    Обработка выбора "Да/Нет" для добавления фотографий
    
    Args:
        message (Message): Сообщение с выбором
        state (FSMContext): Контекст состояния
    """
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    if message.text == "✅ Да":
        # Предлагаем отправить фото
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Готово")],
                [KeyboardButton(text="В меню")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            "Отправьте фотографии результата (можно несколько).\n"
            "Когда закончите — нажмите «✅ Готово»:",
            reply_markup=keyboard
        )
        await state.set_state(PhotoStates.waiting_for_caption)
    else:  # "❌ Нет"
        # Пропускаем добавление фото
        await message.answer("📸 Фотографии не добавлены.")
        await state.clear()
        await return_to_role_menu(message, state, role="provider")


@router.message(PhotoStates.waiting_for_caption, F.photo)
async def save_photo(message: Message, state: FSMContext):
    """
    Сохранение фотографии в БД
    
    Args:
        message (Message): Сообщение с фото
        state (FSMContext): Контекст состояния
    """
    # Получаем самое большое фото из группы
    photo = message.photo[-1]
    
    # Получаем данные из состояния
    data = await state.get_data()
    record_id = data.get('record_id')
    
    if not record_id:
        await message.answer("Ошибка: запись не найдена. Начните заново.")
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Сохраняем фото в БД
    await add_service_photo(
        record_id=record_id,
        photo_file_id=photo.file_id,
        caption=message.caption or "Результат работы"
    )
    
    await message.answer("✅ Фото сохранено! Отправьте ещё или нажмите «✅ Готово».")


@router.message(PhotoStates.waiting_for_caption, F.text == "✅ Готово")
async def finish_photos(message: Message, state: FSMContext):
    """
    Завершение добавления фотографий
    
    Args:
        message (Message): Сообщение с кнопкой "Готово"
        state (FSMContext): Контекст состояния
    """
    await message.answer("📸 Все фотографии сохранены!")
    await state.clear()
    await return_to_role_menu(message, state, role="provider")