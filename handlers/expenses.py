"""
handlers/expenses.py
====================
Обработчик учёта трат мастера
Позволяет добавлять расходы на материалы, транспорт и т.д.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import ExpenseStates
from database import add_expense
from keyboards import cancel_menu_keyboard
from handlers.logout import return_to_role_menu

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём роутер для обработки трат
router = Router()


@router.message(F.text == "Добавить трату")
async def start_expense(message: Message, state: FSMContext):
    """
    Начало процесса добавления траты
    
    Запрашивает сумму траты у мастера
    
    Args:
        message (Message): Входящее сообщение
        state (FSMContext): Контекст состояния
    """
    # Запрашиваем сумму траты
    await message.answer(
        "Введите сумму траты (в рублях):", 
        reply_markup=cancel_menu_keyboard()
    )
    
    # Устанавливаем состояние ожидания суммы
    await state.set_state(ExpenseStates.waiting_for_amount)


@router.message(ExpenseStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    """
    Обработка ввода суммы траты
    
    Проверяет, что введено положительное число
    
    Args:
        message (Message): Сообщение с суммой
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия (нажатие "В меню")
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    try:
        # Преобразуем ввод в целое число
        amount = int(message.text.strip())
        
        # Проверяем положительность суммы
        if amount <= 0:
            raise ValueError
        
        # Сохраняем сумму в состоянии
        await state.update_data(amount=amount)
        
        # Запрашиваем описание траты
        await message.answer(
            "Опишите трату (материалы, транспорт и т.д.):", 
            reply_markup=cancel_menu_keyboard()
        )
        
        # Устанавливаем состояние ожидания описания
        await state.set_state(ExpenseStates.waiting_for_description)
    
    except:
        # Некорректный ввод - просим ввести снова
        await message.answer("Введите положительное число:")


@router.message(ExpenseStates.waiting_for_description)
async def process_description_and_save(message: Message, state: FSMContext):
    """
    Обработка описания траты и сохранение в БД
    
    Сохраняет трату с суммой и описанием
    
    Args:
        message (Message): Сообщение с описанием
        state (FSMContext): Контекст состояния
    """
    # Проверка отмены действия (нажатие "В меню")
    if message.text == "В меню":
        await state.clear()
        await return_to_role_menu(message, state, role="provider")
        return
    
    # Получаем описание траты
    description = message.text.strip()
    
    # Получаем данные из состояния
    data = await state.get_data()
    
    # Сохраняем трату в БД
    await add_expense(
        provider_id=message.from_user.id,
        amount=data['amount'],
        description=description
    )
    
    # Подтверждаем сохранение мастеру
    await message.answer(
        f"✅ Трата сохранена!\n"
        f"Сумма: {data['amount']} руб.\n"
        f"Описание: {description}"
    )
    
    # Очищаем состояние и возвращаемся в меню
    await state.clear()
    await return_to_role_menu(message, state, role="provider")