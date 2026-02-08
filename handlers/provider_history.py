"""
handlers/provider_history.py
============================
Обработчик истории клиентов мастера за месяц
Показывает сводку по клиентам: имя/фамилия, услуги, количество записей
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from database import get_provider_client_history_for_month  # ← Теперь работает!
from keyboards import provider_menu_keyboard, cancel_menu_keyboard
from handlers.logout import return_to_role_menu

router = Router()


@router.message(F.text == "История клиентов")
async def show_provider_client_history(message: Message, state: FSMContext):
    """
    Показывает историю клиентов мастера за последний месяц
    
    Формат:
    • Иван Петров (ID: 000123)
      Ремонт сантехники: 2 записи
      Укладка плитки: 1 запись
      Всего: 3 записи
    
    • Мария Сидорова (ID: 000456)
      Массаж: 1 запись
      Всего: 1 запись
    """
    # Получаем историю клиентов
    history = await get_provider_client_history_for_month(message.from_user.id)
    
    # Формируем сообщение
    if not history:
        await message.answer(
            "У вас нет клиентов за последний месяц.",
            reply_markup=provider_menu_keyboard()
        )
        return
    
    response = "📋 История ваших клиентов за месяц:\n\n"
    for item in history:
        response += f"• {item['full_name']} (ID: {item['user_code']})\n"
        
        # Добавляем услуги
        for service, count in item['services'].items():
            response += f"  {service}: {count} запись(ей)\n"
        
        # Добавляем итог
        response += f"  Всего: {item['total_records']} запись(ей)\n\n"
    
    # Отправляем результат
    await message.answer(
        response.strip(),
        reply_markup=cancel_menu_keyboard()
    )


@router.message(F.text == "В меню")
async def back_to_menu(message: Message, state: FSMContext):
    """Возврат в меню мастера"""
    await return_to_role_menu(message, state, role="provider")