from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from calendar import month_name
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
from FSMstates import CalendarStates

router = Router()

@router.message(F.text == "Календарь")
async def start_calendar(message: Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("user_role")
    
    if role not in ("client", "provider"):
        await message.answer("Сначала войдите в аккаунт.", reply_markup=main_menu_keyboard())
        return

    telegram_id = message.from_user.id
    years = await get_record_years(telegram_id, role)
    
    if not years:
        await message.answer("У вас нет записей.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(role=role, telegram_id=telegram_id)
    await state.set_state(CalendarStates.waiting_for_year)
    await message.answer("Выберите год:", reply_markup=get_years_inline(years))

# === ГОД → МЕСЯЦ ===

@router.callback_query(CalendarStates.waiting_for_year, F.data.startswith("cal_year_"))
async def process_year(callback: CallbackQuery, state: FSMContext):
    year = int(callback.data.split("_")[-1])
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    
    months = await get_record_months(telegram_id, role, year)
    if not months:
        await callback.answer("В этом году нет записей.", show_alert=True)
        return

    await state.update_data(selected_year=year)
    await state.set_state(CalendarStates.waiting_for_month)
    await callback.message.edit_text("Выберите месяц:", reply_markup=get_months_inline(year, months))
    await callback.answer()

@router.callback_query(F.data == "cal_back_year")
async def back_to_year(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    years = await get_record_years(telegram_id, role)
    await state.set_state(CalendarStates.waiting_for_year)
    await callback.message.edit_text("Выберите год:", reply_markup=get_years_inline(years))
    await callback.answer()

# === МЕСЯЦ → КАЛЕНДАРЬ ===

@router.callback_query(CalendarStates.waiting_for_month, F.data.startswith("cal_month_"))
async def process_month(callback: CallbackQuery, state: FSMContext):
    month_num = int(callback.data.split("_")[-1])
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    year = data["selected_year"]
    
    days = await get_record_days(telegram_id, role, year, month_num)
    await state.update_data(selected_month=month_num)
    await state.set_state(CalendarStates.waiting_for_day)
    
    # Отображаем календарь с заголовком
    await callback.message.edit_text(
        f"📅 {month_name[month_num]} {year}\n\nВыберите день:",
        reply_markup=get_calendar_inline(year, month_num, days)
    )
    await callback.answer()

@router.callback_query(F.data == "cal_back_month")
async def back_to_month(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    year = data["selected_year"]
    month = data["selected_month"]
    
    days = await get_record_days(telegram_id, role, year, month)
    await state.set_state(CalendarStates.waiting_for_day)
    await callback.message.edit_text(
        f"📅 {month_name[month]} {year}\n\nВыберите день:",
        reply_markup=get_calendar_inline(year, month, days)
    )
    await callback.answer()

# === ДЕНЬ → ЗАПИСИ ===

@router.callback_query(F.data.startswith("cal_day_"))
async def process_day(callback: CallbackQuery, state: FSMContext):
    day = int(callback.data.split("_")[-1])
    data = await state.get_data()
    role = data["role"]
    telegram_id = data["telegram_id"]
    year = data["selected_year"]
    month = data["selected_month"]
    
    records = await get_records_by_date(telegram_id, role, year, month, day)
    if not records:
        await callback.answer("На эту дату записей нет.", show_alert=True)
        return

    response = f"📅 Записи на {day:02d}.{month:02d}.{year}:\n\n"
    for record in records:
        response += (
            f"🔹 {record['service_name']}\n"
            f"   Время: {record['service_time']}\n"
            f"   Адрес: {record['address']}\n"
            f"   Комментарии: {record['comments']}\n\n"
        )
    
    await callback.message.edit_text(response.strip())

# === НАВИГАЦИЯ ===

@router.callback_query(F.data == "cal_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Вы вернулись в главное меню.", reply_markup=main_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    await callback.answer()