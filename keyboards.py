# keyboards.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from calendar import month_name
from datetime import datetime

def main_menu_keyboard(is_registered: bool = False):
    if not is_registered:
        # Только для незарегистрированных
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Зарегистрироваться")]
            ],
            resize_keyboard=True
        )
    else:
        # Только для зарегистрированных
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Войти как предоставитель услуги")],
                [KeyboardButton(text="Войти как клиент")]
            ],
            resize_keyboard=True
        )

# ... остальные клавиатуры без изменений ...

def client_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Связаться с мастером")],
            [KeyboardButton(text="Календарь")],
            [KeyboardButton(text="Сбросить пароль")],
            [KeyboardButton(text="Выйти из аккаунта")]
        ],
        resize_keyboard=True
    )

def provider_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Добавить запись")],
            [KeyboardButton(text="Календарь")],
            [KeyboardButton(text="Сбросить пароль")],
            [KeyboardButton(text="Выйти из аккаунта")]
        ],
        resize_keyboard=True
    )

def client_chat_active_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Завершить чат")]
        ],
        resize_keyboard=True
    )

def provider_chat_active_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Завершить чат")]
        ],
        resize_keyboard=True
    )

def cancel_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="В меню")]],
        resize_keyboard=True
    )

def password_reset_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сбросить пароль", callback_data="reset_password_from_login")]
    ])

def chat_request_inline(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_chat_{chat_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_chat_{chat_id}")
        ]
    ])

# === INLINE-КЛАВИАТУРЫ ДЛЯ КАЛЕНДАРЯ ===

def get_years_inline(years: list[int]) -> InlineKeyboardMarkup:
    buttons = []
    for year in sorted(years, reverse=True):
        buttons.append([InlineKeyboardButton(text=str(year), callback_data=f"cal_year_{year}")])
    buttons.append([InlineKeyboardButton(text="🏠 В меню", callback_data="cal_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_months_inline(year: int, month_counts: dict[int, int]) -> InlineKeyboardMarkup:
    current_year = datetime.now().year
    current_month = datetime.now().month
    buttons = []
    row = []
    for month_num in sorted(month_counts.keys()):
        if year > current_year or (year == current_year and month_num >= current_month):
            month_label = f"{month_name[month_num]}"
            row.append(InlineKeyboardButton(text=month_label, callback_data=f"cal_month_{month_num}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад к выбору года", callback_data="cal_back_year")])
    buttons.append([InlineKeyboardButton(text="🏠 В меню", callback_data="cal_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_calendar_inline(year: int, month: int, day_counts: dict[int, int]) -> InlineKeyboardMarkup:
    """Создаёт календарную сетку в стиле изображения"""
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    from calendar import monthrange
    first_day, num_days = monthrange(year, month)
    
    buttons = []
    row = [InlineKeyboardButton(text=dow, callback_data="ignore") for dow in days_of_week]
    buttons.append(row)
    
    current_row = [InlineKeyboardButton(text=" ", callback_data="ignore") for _ in range(first_day)]
    
    for day in range(1, num_days + 1):
        if day in day_counts:
            label = f"{day} ({day_counts[day]})"
        else:
            label = str(day)
        current_row.append(InlineKeyboardButton(text=label, callback_data=f"cal_day_{day}"))
        if len(current_row) == 7:
            buttons.append(current_row)
            current_row = []
    
    while len(current_row) < 7:
        current_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
    if current_row:
        buttons.append(current_row)
    
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к месяцу", callback_data="cal_back_month"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="cal_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)