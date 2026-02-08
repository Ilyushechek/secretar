"""
handlers/cancellation.py
========================
Обработчик отмены активных записей на услуги
Позволяет мастеру выбрать и отменить запись
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import CancellationStates
from database import (
    get_active_records_for_provider,
    cancel_service_record,
    get_user_name,
    get_client_from_record,
    create_notification
)
from keyboards import cancel_menu_keyboard
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки отмены записей
router = Router()


@router.message(F.text == "Отменить запись")
async def start_cancellation(message: Message, state: FSMContext):
    """
    Начало процесса отмены записи
    
    Показывает список активных записей для выбора
    
    Args:
        message (Message): Входящее сообщение
        state (FSMContext): Контекст состояния
    """
    # Получаем активные записи мастера
    records = await get_active_records_for_provider(message.from_user.id)
    
    # Проверяем наличие записей
    if not records:
        await message.answer("У вас нет активных записей для отмены.")
        return
    
    # Формируем сообщение со списком записей
    response = "Выберите запись для отмены:\n\n"
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
    await state.set_state(CancellationStates.waiting_for_record_id)


@router.message(CancellationStates.waiting_for_record_id)
async def process_cancellation(message: Message, state: FSMContext):
    """
    Обработка выбора записи для отмены
    
    Отменяет запись в БД и уведомляет клиента
    
    Args:
        message (Message): Сообщение с номером записи
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия (нажатие "В меню")
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
        
        # Получаем ID записи для отмены
        record_id = records[record_num]['id']
        
        # Отменяем запись в БД (проверяем, что запись принадлежит мастеру)
        success = await cancel_service_record(record_id, message.from_user.id)
        
        if success:
            # Уведомляем клиента об отмене записи
            client_id = await get_client_from_record(record_id)
            if client_id:
                service_name = records[record_num]['service_name']
                service_date = records[record_num]['service_date']
                service_time = records[record_num]['service_time']
                try:
                    await create_notification(
                        telegram_id=client_id,
                        role="client",
                        message_text=(
                            f"❌ Мастер отменил запись '{service_name}' "
                            f"на {service_date} {service_time}."
                        )
                    )
                except Exception as e:
                    logger.error(f"Ошибка создания уведомления клиенту: {e}")
            
            # Подтверждаем отмену мастеру
            await message.answer(f"✅ Запись отменена!")
        else:
            # Ошибка отмены (запись уже отменена или завершена)
            await message.answer(
                "❌ Не удалось отменить запись. "
                "Возможно, она уже завершена или отменена."
            )
    except Exception as e:
        # Обработка ошибок (некорректный ввод, ошибка БД и т.д.)
        logger.error(f"Ошибка отмены записи: {e}")
        await message.answer(
            f"Неверный номер. Введите число от 1 до {len(records)}:", 
            reply_markup=cancel_menu_keyboard()
        )
    
    # Очищаем состояние и возвращаемся в меню
    await state.clear()
    await return_to_role_menu(message, state, role="provider")