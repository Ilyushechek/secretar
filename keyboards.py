"""
keyboards.py
============
Модуль для создания клавиатур (кнопок) в интерфейсе бота
Поддерживает как обычные (Reply), так и inline-клавиатуры
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from calendar import month_name
from datetime import datetime


# ============================================================================
# ГЛАВНОЕ МЕНЮ (с учётом регистрации и счётчиков уведомлений)
# ============================================================================

def main_menu_keyboard(is_registered: bool = False, client_count: int = 0, provider_count: int = 0):
    """
    Создаёт главное меню в зависимости от статуса регистрации
    
    Args:
        is_registered (bool): Зарегистрирован ли пользователь
        client_count (int): Количество непрочитанных уведомлений для клиента
        provider_count (int): Количество непрочитанных уведомлений для мастера
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура главного меню
    """
    if not is_registered:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Зарегистрироваться")]
            ],
            resize_keyboard=True
        )
    else:
        client_text = f"Войти как клиент ({client_count})" if client_count > 0 else "Войти как клиент"
        provider_text = f"Войти как предоставитель услуги ({provider_count})" if provider_count > 0 else "Войти как предоставитель услуги"
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=provider_text)],
                [KeyboardButton(text=client_text)],
                [KeyboardButton(text="Сбросить пароль")]
            ],
            resize_keyboard=True
        )


# ============================================================================
# МЕНЮ КЛИЕНТА (после успешного входа)
# ============================================================================

def client_menu_keyboard():
    """
    Создаёт компактное меню для авторизованного клиента (2 колонки)
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Связаться с мастером"),
                KeyboardButton(text="Календарь")
            ],
            [
                KeyboardButton(text="История записей"),
                KeyboardButton(text="👤 Профиль мастера")
            ],
            [
                KeyboardButton(text="Сбросить пароль"),
                KeyboardButton(text="Выйти из аккаунта")
            ]
        ],
        resize_keyboard=True
    )


# ============================================================================
# МЕНЮ МАСТЕРА (после успешного входа)
# ============================================================================

def provider_menu_keyboard():
    """
    Создаёт компактное меню для авторизованного мастера (2 колонки)
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Добавить запись"),
                KeyboardButton(text="Завершить услугу")
            ],
            [
                KeyboardButton(text="Отменить запись"),
                KeyboardButton(text="Статистика")
            ],
            [
                KeyboardButton(text="Траты"),
                KeyboardButton(text="📥 Запросы")
            ],
            [
                KeyboardButton(text="📍 Адреса работы"),
                KeyboardButton(text="🔧 Мои услуги")
            ],
            [
                KeyboardButton(text="📸 Фото профиля"),
                KeyboardButton(text="Календарь")
            ],
            [
                KeyboardButton(text="Сбросить пароль"),
                KeyboardButton(text="Выйти из аккаунта")
            ]
        ],
        resize_keyboard=True
    )


# ============================================================================
# КЛАВИАТУРЫ АКТИВНОГО ЧАТА
# ============================================================================

def client_chat_active_keyboard():
    """Клавиатура для клиента во время активного чата"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Завершить чат")]
        ],
        resize_keyboard=True
    )


def provider_chat_active_keyboard():
    """Клавиатура для мастера во время активного чата"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Завершить чат")]
        ],
        resize_keyboard=True
    )


# ============================================================================
# КЛАВИАТУРА ОТМЕНЫ
# ============================================================================

def cancel_menu_keyboard():
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


# ============================================================================
# INLINE-КЛАВИАТУРЫ
# ============================================================================

def password_reset_inline():
    """Inline-кнопка для сброса пароля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Сбросить пароль", 
                callback_data="reset_password_from_login"
            )
        ]
    ])


def chat_request_inline(chat_id: int):
    """Inline-клавиатура запроса на чат"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_chat_{chat_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_chat_{chat_id}")
        ]
    ])


def create_record_after_chat_inline(chat_id: int):
    """Inline-клавиатура подтверждения создания записи после чата"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"create_record_yes_{chat_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"create_record_no_{chat_id}")
        ]
    ])


def statistics_period_keyboard():
    """Клавиатура выбора периода статистики"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 За день")],
            [KeyboardButton(text="📅 За неделю")],
            [KeyboardButton(text="📆 За месяц")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def yes_no_keyboard():
    """Универсальная клавиатура Да/Нет"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да")],
            [KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )


# ============================================================================
# КЛАВИАТУРЫ ЗАПРОСОВ ПОВТОРНОЙ ЗАПИСИ
# ============================================================================

def repeat_request_menu_keyboard():
    """Клавиатура меню запросов для клиента"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Выбрать из истории")],
            [KeyboardButton(text="🔍 Найти мастера")],
            [KeyboardButton(text="📋 Мои запросы")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def search_type_keyboard():
    """Клавиатура выбора типа поиска"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="По услуге")],
            [KeyboardButton(text="По имени мастера")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def provider_requests_menu_keyboard():
    """Клавиатура меню запросов для мастера"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Новые запросы")],
            [KeyboardButton(text="💬 Мои диалоги")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def request_action_keyboard():
    """Клавиатура действий с запросом (мастер)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Принять")],
            [KeyboardButton(text="❌ Отклонить")],
            [KeyboardButton(text="✏️ Ответить")],
            [KeyboardButton(text="📄 Создать запись")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def client_request_action_keyboard():
    """Клавиатура действий с запросом (клиент)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Написать ответ")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


# ============================================================================
# КЛАВИАТУРЫ ОЦЕНОК И ОТЗЫВОВ
# ============================================================================

def rating_keyboard():
    """Клавиатура выбора оценки (1-5 звёзд)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⭐"),
                KeyboardButton(text="⭐⭐"),
                KeyboardButton(text="⭐⭐⭐"),
                KeyboardButton(text="⭐⭐⭐⭐"),
                KeyboardButton(text="⭐⭐⭐⭐⭐")
            ],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def cancel_inline_keyboard():
    """
    Инлайн-клавиатура с кнопкой отмены для редактируемых сообщений
    Используется вместо обычной клавиатуры при вызове edit_text()
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В меню", callback_data="cancel_action")]
    ])


# ============================================================================
# КЛАВИАТУРЫ ПРОСМОТРА ПРОФИЛЯ МАСТЕРА
# ============================================================================

def profile_search_method_keyboard():
    """Клавиатура выбора способа поиска мастера"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 По ID мастера")],
            [KeyboardButton(text="📋 Из истории записей")],
            [KeyboardButton(text="В меню")]
        ],
        resize_keyboard=True
    )


def profile_actions_keyboard(provider_id: int):
    """Клавиатура действий с профилем мастера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⭐ Отзывы",
                callback_data=f"profile_reviews_{provider_id}"
            ),
            InlineKeyboardButton(
                text="📅 Записаться",
                callback_data=f"profile_book_{provider_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Выбрать другого мастера",
                callback_data="profile_search_again"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="profile_menu"
            )
        ]
    ])


# ============================================================================
# INLINE-КЛАВИАТУРЫ КАЛЕНДАРЯ
# ============================================================================

def get_years_inline(years: list[int]) -> InlineKeyboardMarkup:
    """Inline-клавиатура выбора года"""
    buttons = []
    for year in sorted(years, reverse=True):
        buttons.append([
            InlineKeyboardButton(text=str(year), callback_data=f"cal_year_{year}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🏠 В меню", callback_data="cal_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_months_inline(year: int, month_counts: dict[int, int]) -> InlineKeyboardMarkup:
    """Inline-клавиатура выбора месяца"""
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
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к выбору года", callback_data="cal_back_year")
    ])
    buttons.append([
        InlineKeyboardButton(text="🏠 В меню", callback_data="cal_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_calendar_inline(year: int, month: int, day_counts: dict[int, int]) -> InlineKeyboardMarkup:
    """Календарная сетка"""
    from calendar import monthrange
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    first_day, num_days = monthrange(year, month)
    
    buttons = []
    row = [InlineKeyboardButton(text=dow, callback_data="ignore") for dow in days_of_week]
    buttons.append(row)
    
    current_row = [InlineKeyboardButton(text=" ", callback_data="ignore") for _ in range(first_day)]
    
    for day in range(1, num_days + 1):
        label = f"{day} ({day_counts[day]})" if day in day_counts else str(day)
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