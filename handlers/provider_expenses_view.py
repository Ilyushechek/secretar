"""
handlers/provider_expenses_view.py
==================================
Обработчик просмотра трат мастера за месяц
Показывает список всех трат с суммами и описаниями
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from database import get_expenses_for_month  # ← Теперь работает!
from keyboards import provider_menu_keyboard, cancel_menu_keyboard
from handlers.logout import return_to_role_menu

router = Router()


@router.message(F.text == "Траты")
async def show_provider_expenses(message: Message, state: FSMContext):
    """
    Показывает все траты мастера за текущий месяц
    
    Формат:
    💰 Траты за месяц:
    
    15.01.2026 14:30
    Материалы для ремонта
    Сумма: 2 500 руб.
    
    10.01.2026 09:15
    Транспорт
    Сумма: 350 руб.
    
    ---
    Итого: 2 850 руб.
    """
    # Получаем траты за месяц
    expenses = await get_expenses_for_month(message.from_user.id)
    
    # Формируем сообщение
    if not expenses:
        await message.answer(
            "У вас нет трат за текущий месяц.",
            reply_markup=provider_menu_keyboard()
        )
        return
    
    response = "💰 Ваши траты за месяц:\n\n"
    total = 0
    
    for i, expense in enumerate(expenses, 1):
        date_str = expense['created_at'].strftime('%d.%m.%Y %H:%M')
        amount = expense['amount']
        description = expense['description']
        
        response += f"{date_str}\n"
        response += f"{description}\n"
        response += f"Сумма: {amount} руб.\n\n"
        
        total += amount
    
    # Добавляем итог
    response += f"---\nИтого: {total} руб."
    
    # Отправляем результат
    await message.answer(
        response,
        reply_markup=cancel_menu_keyboard()
    )


@router.message(F.text == "В меню")
async def back_to_menu(message: Message, state: FSMContext):
    """Возврат в меню мастера"""
    await return_to_role_menu(message, state, role="provider")