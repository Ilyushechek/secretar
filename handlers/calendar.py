"""
handlers/calendar.py
====================
Обработчик календаря записей.
Навигация: год → месяц → день → список записей.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from calendar import month_name
from FSMstates import CalendarStates
from database import (
    get_record_years,
    get_record_months,
    get_record_days,
    get_records_by_date
)
from keyboards import (
    get_years_inline,
    get_months_inline,
    get_calendar_inline,
    main_menu_keyboard
)
from handlers.logout import return_to_role_menu  # ← ПРАВИЛЬНЫЙ ИМПОРТ ФУНКЦИИ

# Создаём роутер для обработки календаря
router = Router()


@router.message(F.text == "Календарь")
async def start_calendar(message: Message, state: FSMContext):
    """
    Начало навигации по календарю.
    
    Показывает список доступных годов с записями.
    """
    # Получаем роль пользователя из состояния
    data = await state.get_data()
    role = data.get("user_role")
    
    # Проверяем авторизацию
    if role not in ("client", "provider"):
        await message.answer(
            "Сначала войдите в аккаунт.", 
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Получаем список годов с записями для пользователя
    telegram_id = message.from_user.id
    years = await get_record_years(telegram_id, role)
    
    # Проверяем наличие записей
    if not years:
        await message.answer(
            "У вас нет записей.", 
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Сохраняем роль и ID для последующих шагов
    await state.update_data(role=role, telegram_id=telegram_id)
    
    # Устанавливаем состояние выбора года
    await state.set_state(CalendarStates.waiting_for_year)
    
    # Показываем список годов
    await message.answer(
        "Выберите год:", 
        reply_markup=get_years_inline(years)
    )


# ============================================================================
# ВЫБОР ГОДА
# ============================================================================

@router.callback_query(CalendarStates.waiting_for_year, F.data.startswith("cal_year_"))
async def process_year(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора года.
    
    Показывает список месяцев с записями в выбранном году.
    """
    # Извлекаем год из callback_data
    year = int(callback.data.split("_")[-1])
    
    # Получаем данные из состояния
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    
    # Получаем месяцы с записями в этом году
    months = await get_record_months(telegram_id, role, year)
    if not months:
        await callback.answer("В этом году нет записей.", show_alert=True)
        return
    
    # Сохраняем выбранный год
    await state.update_data(selected_year=year)
    
    # Устанавливаем состояние выбора месяца
    await state.set_state(CalendarStates.waiting_for_month)
    
    # Редактируем сообщение на список месяцев
    await callback.message.edit_text(
        "Выберите месяц:", 
        reply_markup=get_months_inline(year, months)
    )
    
    # Подтверждаем нажатие кнопки
    await callback.answer()


@router.callback_query(F.data == "cal_back_year")
async def back_to_year(callback: CallbackQuery, state: FSMContext):
    """
    Возврат к выбору года из месяца.
    """
    # Получаем данные из состояния
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    
    # Получаем список годов
    years = await get_record_years(telegram_id, role)
    
    # Устанавливаем состояние выбора года
    await state.set_state(CalendarStates.waiting_for_year)
    
    # Редактируем сообщение на список годов
    await callback.message.edit_text(
        "Выберите год:", 
        reply_markup=get_years_inline(years)
    )
    
    # Подтверждаем нажатие кнопки
    await callback.answer()


# ============================================================================
# ВЫБОР МЕСЯЦА
# ============================================================================

@router.callback_query(CalendarStates.waiting_for_month, F.data.startswith("cal_month_"))
async def process_month(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора месяца.
    
    Показывает календарную сетку дней с записями.
    """
    # Извлекаем номер месяца
    month_num = int(callback.data.split("_")[-1])
    
    # Получаем данные из состояния
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    year = data["selected_year"]
    
    # Получаем дни с записями в этом месяце
    days = await get_record_days(telegram_id, role, year, month_num)
    
    # Сохраняем выбранный месяц
    await state.update_data(selected_month=month_num)
    
    # Устанавливаем состояние выбора дня
    await state.set_state(CalendarStates.waiting_for_day)
    
    # Редактируем сообщение на календарную сетку
    await callback.message.edit_text(
        f"📅 {month_name[month_num]} {year}\n\nВыберите день:",
        reply_markup=get_calendar_inline(year, month_num, days)
    )
    
    # Подтверждаем нажатие кнопки
    await callback.answer()


@router.callback_query(F.data == "cal_back_month")
async def back_to_month(callback: CallbackQuery, state: FSMContext):
    """
    Возврат к выбору месяца из дня.
    """
    # Получаем данные из состояния
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    year = data["selected_year"]
    
    # Получаем месяцы в этом году
    months = await get_record_months(telegram_id, role, year)
    
    # Устанавливаем состояние выбора месяца
    await state.set_state(CalendarStates.waiting_for_month)
    
    # Редактируем сообщение на список месяцев
    await callback.message.edit_text(
        "Выберите месяц:", 
        reply_markup=get_months_inline(year, months)
    )
    
    # Подтверждаем нажатие кнопки
    await callback.answer()


# ============================================================================
# ВЫБОР ДНЯ
# ============================================================================

@router.callback_query(F.data.startswith("cal_day_"))
async def process_day(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора дня.
    
    Показывает список записей на выбранный день.
    """
    # Извлекаем номер дня
    day = int(callback.data.split("_")[-1])
    
    # Получаем данные из состояния
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    year = data["selected_year"]
    month = data["selected_month"]
    
    # Получаем записи на этот день
    records = await get_records_by_date(telegram_id, role, year, month, day)
    if not records:
        await callback.answer("На эту дату записей нет.", show_alert=True)
        return
    
    # Формируем сообщение со списком записей
    response = f"📅 Записи на {day:02d}.{month:02d}.{year}:\n\n"
    for record in records:
        response += (
            f"🔹 {record['service_name']}\n"
            f"   Время: {record['service_time']}\n"
            f"   Адрес: {record['address']}\n"
            f"   Комментарии: {record['comments']}\n\n"
        )
    
    # Редактируем сообщение на список записей
    await callback.message.edit_text(response.strip())
    
    # Подтверждаем нажатие кнопки
    await callback.answer()


# ============================================================================
# НАВИГАЦИЯ
# ============================================================================

@router.callback_query(F.data == "cal_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """
    Возврат в главное меню из календаря.
    """
    # Очищаем состояние
    await state.clear()
    
    # Редактируем сообщение на главное меню
    await callback.message.edit_text(
        "Вы вернулись в главное меню.", 
        reply_markup=main_menu_keyboard()
    )
    
    # Подтверждаем нажатие кнопки
    await callback.answer()


@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    """
    Игнорирование нажатия на пустые ячейки календаря.
    """
    # Просто подтверждаем нажатие без действия
    await callback.answer()