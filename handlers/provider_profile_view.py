"""
handlers/provider_profile_view.py
==================================
Просмотр профиля мастера и его отзывов клиентом
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton  # ← ОБЯЗАТЕЛЬНО!
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import ProfileViewStates
from database import (
    get_provider_profile,
    get_client_provider_history,
    get_user_telegram_id_by_code
)
from keyboards import (
    profile_search_method_keyboard,
    profile_actions_keyboard,
    client_menu_keyboard,
    cancel_menu_keyboard
)
from handlers.logout import return_to_role_menu  # ← ПРАВИЛЬНЫЙ ИМПОРТ ФУНКЦИИ

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "👤 Профиль мастера")
async def start_profile_view(message: Message, state: FSMContext):
    """
    Начало просмотра профиля мастера
    
    Предлагает выбрать способ поиска: по ID или из истории записей
    """
    await message.answer(
        "Как найти мастера для просмотра профиля?\n"
        "• 🔍 По ID — введите 6-значный код мастера\n"
        "• 📋 Из истории — выберите из мастеров, к которым вы записывались",
        reply_markup=profile_search_method_keyboard()
    )
    await state.set_state(ProfileViewStates.choosing_search_method)


@router.message(ProfileViewStates.choosing_search_method, F.text == "🔍 По ID мастера")
async def start_search_by_id(message: Message, state: FSMContext):
    """Начало поиска мастера по ID"""
    await message.answer(
        "Введите 6-значный ID мастера:",
        reply_markup=cancel_menu_keyboard()
    )
    await state.set_state(ProfileViewStates.entering_provider_id)


@router.message(ProfileViewStates.entering_provider_id)
async def process_provider_id(message: Message, state: FSMContext):
    """Обработка ввода ID мастера и показ профиля"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="client")
        return
    
    # Проверяем формат ID (6 цифр)
    user_code = message.text.strip()
    if not user_code.isdigit() or len(user_code) != 6:
        await message.answer(
            "Неверный формат ID. Введите 6 цифр:",
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Получаем telegram_id по коду
    provider_telegram_id = await get_user_telegram_id_by_code(user_code)
    if not provider_telegram_id:
        await message.answer(
            "Мастер с таким ID не найден. Попробуйте снова:",
            reply_markup=cancel_menu_keyboard()
        )
        return
    
    # Получаем полный профиль мастера
    profile = await get_provider_profile(provider_telegram_id)
    if not profile:
        await message.answer(
            "Не удалось загрузить профиль мастера.",
            reply_markup=client_menu_keyboard()
        )
        return
    
    # Сохраняем профиль в состоянии для последующих действий
    await state.update_data(current_provider=profile)
    
    # Показываем профиль
    await show_provider_profile(message, profile)


@router.message(ProfileViewStates.choosing_search_method, F.text == "📋 Из истории записей")
async def show_history_for_profile_selection(message: Message, state: FSMContext):
    """Показывает историю мастеров для выбора профиля"""
    # Получаем историю мастеров клиента
    history = await get_client_provider_history(message.from_user.id)
    
    if not history:
        await message.answer(
            "У вас нет истории записей к мастерам.\n"
            "Сначала запишитесь на услугу, чтобы появилась история.",
            reply_markup=client_menu_keyboard()
        )
        await state.clear()
        return
    
    # Формируем пронумерованный список мастеров
    response = "📋 Выберите мастера из истории:\n\n"
    for i, provider in enumerate(history, 1):
        # Формируем строку рейтинга
        if provider['review_count'] > 0:
            rating_str = f" ⭐{provider['average_rating']:.1f} ({provider['review_count']})"
        else:
            rating_str = ""
        
        response += (
            f"{i}. {provider['full_name']} (ID: {provider['user_code']}){rating_str}\n"
            f"   Записей: {provider['total_records']}\n"
            f"   Услуги: {provider['services_list'][:40]}...\n\n"
        )
    
    response += "Введите номер мастера для просмотра профиля:"
    
    # Сохраняем историю в состоянии
    await state.update_data(provider_history=history)
    await message.answer(response, reply_markup=cancel_menu_keyboard())
    await state.set_state(ProfileViewStates.choosing_from_history)


@router.message(ProfileViewStates.choosing_from_history)
async def process_history_selection(message: Message, state: FSMContext):
    """Обработка выбора мастера из истории"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="client")
        return
    
    try:
        # Преобразуем ввод в индекс (нумерация с 1)
        provider_num = int(message.text.strip()) - 1
        
        # Получаем данные из состояния
        data = await state.get_data()
        history = data.get('provider_history', [])
        
        # Проверяем корректность индекса
        if provider_num < 0 or provider_num >= len(history):
            raise ValueError
        
        # Получаем выбранного мастера
        selected_provider = history[provider_num]
        provider_id = selected_provider['provider_id']
        
        # Получаем полный профиль мастера
        profile = await get_provider_profile(provider_id)
        if not profile:
            await message.answer(
                "Не удалось загрузить профиль мастера.",
                reply_markup=client_menu_keyboard()
            )
            return
        
        # Сохраняем профиль в состоянии
        await state.update_data(current_provider=profile)
        
        # Показываем профиль
        await show_provider_profile(message, profile)
    
    except (ValueError, IndexError):
        await message.answer(
            f"Неверный номер. Введите число от 1 до {len(history)}:",
            reply_markup=cancel_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка выбора мастера из истории: {e}")
        await message.answer(
            "Произошла ошибка. Попробуйте снова.",
            reply_markup=client_menu_keyboard()
        )
        await state.clear()


async def show_provider_profile(message: Message, profile: dict):
    """
    Отображает полный профиль мастера с фото, рейтингом и услугами
    
    Args:
        message (Message): Сообщение для ответа
        profile (dict): Данные профиля мастера
    """
    # Формируем текст профиля
    response = f"👤 <b>{profile['full_name']}</b> (ID: {profile['user_code']})\n\n"
    
    # Рейтинг
    if profile['review_count'] > 0:
        stars = "⭐" * int(profile['average_rating']) + "☆" * (5 - int(profile['average_rating']))
        response += f"Рейтинг: {stars} {profile['average_rating']:.1f} ({profile['review_count']} отзывов)\n"
    else:
        response += "Рейтинг: ⭐ Без отзывов\n"
    
    # Статистика
    response += f"👥 Клиентов: {profile['client_base']}\n"
    response += f"✅ Услуг: {profile['completed_services']}\n\n"
    
    # Услуги
    if profile['services']:
        response += "🔧 <b>Услуги:</b>\n"
        for srv in profile['services']:
            price_tag = f" 💰{srv['price_range']}" if srv['price_range'] else ""
            response += f"• {srv['service_name']}{price_tag}\n"
            if srv['description']:
                response += f"  {srv['description'][:50]}...\n"
        response += "\n"
    
    # Адреса
    if profile['addresses']:
        response += "📍 <b>Адреса работы:</b>\n"
        for addr in profile['addresses']:
            prefix = "⭐ " if addr['is_primary'] else ""
            response += f"{prefix}{addr['address']}\n"
        response += "\n"
    
    # Последние отзывы (кратко)
    if profile['reviews']:
        response += "💬 <b>Последние отзывы:</b>\n"
        for i, rev in enumerate(profile['reviews'][:3], 1):
            stars = "⭐" * rev['rating']
            date_str = rev['created_at'].strftime('%d.%m.%Y')
            response += f"{i}. {stars} ({date_str})\n   «{rev['comment'][:40]}...»\n"
        if len(profile['reviews']) > 3:
            response += f"\n... и ещё {len(profile['reviews']) - 3} отзывов"
    
    # Отправляем фото профиля (если есть) + текст
    if profile['profile_photo_file_id']:
        try:
            await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=profile['profile_photo_file_id'],
                caption=response,
                parse_mode="HTML",
                reply_markup=profile_actions_keyboard(profile['provider_id'])
            )
            return
        except Exception as e:
            logger.warning(f"Не удалось отправить фото профиля: {e}")
            # Продолжаем без фото
    
    # Отправляем только текст (если нет фото или ошибка отправки)
    await message.answer(
        response,
        parse_mode="HTML",
        reply_markup=profile_actions_keyboard(profile['provider_id'])
    )


@router.callback_query(F.data.startswith("profile_reviews_"))
async def show_provider_reviews(callback: CallbackQuery, state: FSMContext):
    """Показывает все отзывы о мастере (с поддержкой фото-сообщений)"""
    await callback.answer()
    
    # Извлекаем ID мастера
    provider_id = int(callback.data.split("_")[-1])
    
    # Получаем полный профиль (включая все отзывы)
    profile = await get_provider_profile(provider_id)
    if not profile:
        # Безопасное редактирование: проверяем тип сообщения
        if callback.message.text:
            await callback.message.edit_text("❌ Профиль мастера не найден.")
        else:
            await callback.message.edit_caption(caption="❌ Профиль мастера не найден.")
        return
    
    # Формируем список отзывов
    if not profile['reviews']:
        response = f"У мастера {profile['full_name']} пока нет отзывов."
        # Безопасное редактирование в зависимости от типа сообщения
        if callback.message.text:
            await callback.message.edit_text(
                response,
                reply_markup=profile_actions_keyboard(provider_id)
            )
        else:
            await callback.message.edit_caption(
                caption=response,
                reply_markup=profile_actions_keyboard(provider_id)
            )
        return
    
    response = f"⭐ Отзывы о мастере {profile['full_name']} ({profile['review_count']} отзывов):\n\n"
    
    for i, rev in enumerate(profile['reviews'], 1):
        stars = "⭐" * rev['rating']
        date_str = rev['created_at'].strftime('%d.%m.%Y')
        response += (
            f"{i}. {stars} ({date_str})\n"
            f"   {rev['client_name']} (ID: {rev['client_code']})\n"
            f"   «{rev['comment']}»\n\n"
        )
    
    # Обрезаем до 1024 символов (лимит caption для фото в Telegram)
    if len(response) > 1024:
        response = response[:1021] + "..."
    
    # Создаём инлайн-клавиатуру для возврата
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data=f"profile_back_{provider_id}")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="profile_menu")]
    ])
    
    # Безопасное редактирование в зависимости от типа сообщения
    try:
        if callback.message.text:
            # Текстовое сообщение — редактируем текст
            await callback.message.edit_text(
                response,
                reply_markup=back_keyboard
            )
        else:
            # Фото/документ — редактируем подпись (caption)
            await callback.message.edit_caption(
                caption=response,
                reply_markup=back_keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        # Если редактирование не удалось — отправляем новое сообщение
        await callback.message.answer(
            response,
            reply_markup=back_keyboard
        )


@router.callback_query(F.data.startswith("profile_back_"))
async def back_to_profile(callback: CallbackQuery, state: FSMContext):
    """Возврат к просмотру профиля после отзывов (с поддержкой фото-сообщений)"""
    await callback.answer()
    
    provider_id = int(callback.data.split("_")[-1])
    profile = await get_provider_profile(provider_id)
    
    if not profile:
        error_msg = "❌ Профиль не найден."
        if callback.message.text:
            await callback.message.edit_text(
                error_msg,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="profile_menu")]
                ])
            )
        else:
            await callback.message.edit_caption(
                caption=error_msg,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="profile_menu")]
                ])
            )
        return
    
    # Формируем текст профиля (без обрезки — будет обрезано при отправке)
    profile_text = f"👤 <b>{profile['full_name']}</b> (ID: {profile['user_code']})\n\n"
    
    # Рейтинг
    if profile['review_count'] > 0:
        stars = "⭐" * int(profile['average_rating']) + "☆" * (5 - int(profile['average_rating']))
        profile_text += f"Рейтинг: {stars} {profile['average_rating']:.1f} ({profile['review_count']} отзывов)\n"
    else:
        profile_text += "Рейтинг: ⭐ Без отзывов\n"
    
    # Статистика
    profile_text += f"👥 Клиентов: {profile['client_base']}\n"
    profile_text += f"✅ Услуг: {profile['completed_services']}\n\n"
    
    # Услуги
    if profile['services']:
        profile_text += "🔧 <b>Услуги:</b>\n"
        for srv in profile['services'][:3]:  # Ограничиваем 3 услугами для компактности
            price_tag = f" 💰{srv['price_range']}" if srv['price_range'] else ""
            profile_text += f"• {srv['service_name']}{price_tag}\n"
        if len(profile['services']) > 3:
            profile_text += f"... и ещё {len(profile['services']) - 3} услуг\n"
        profile_text += "\n"
    
    # Адреса
    if profile['addresses']:
        profile_text += "📍 <b>Адреса работы:</b>\n"
        for addr in profile['addresses'][:2]:  # Ограничиваем 2 адресами
            prefix = "⭐ " if addr['is_primary'] else ""
            profile_text += f"{prefix}{addr['address']}\n"
        if len(profile['addresses']) > 2:
            profile_text += f"... и ещё {len(profile['addresses']) - 2} адресов\n"
        profile_text += "\n"
    
    # Последние отзывы (кратко)
    if profile['reviews']:
        profile_text += "💬 <b>Последние отзывы:</b>\n"
        for i, rev in enumerate(profile['reviews'][:2], 1):  # Ограничиваем 2 отзывами
            stars = "⭐" * rev['rating']
            date_str = rev['created_at'].strftime('%d.%m.%Y')
            profile_text += f"{i}. {stars} ({date_str})\n   «{rev['comment'][:40]}...»\n"
        if len(profile['reviews']) > 2:
            profile_text += f"\n... и ещё {len(profile['reviews']) - 2} отзывов"
    
    # Безопасное редактирование в зависимости от типа сообщения
    try:
        if callback.message.text:
            # Текстовое сообщение — редактируем текст
            await callback.message.edit_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=profile_actions_keyboard(provider_id)
            )
        else:
            # Фото — редактируем подпись (ограничение 1024 символа)
            caption = profile_text[:1024] if len(profile_text) > 1024 else profile_text
            await callback.message.edit_caption(
                caption=caption,
                parse_mode="HTML",
                reply_markup=profile_actions_keyboard(provider_id)
            )
    except Exception as e:
        logger.error(f"Ошибка возврата к профилю: {e}")
        # Если редактирование не удалось — отправляем новое сообщение с фото
        if profile['profile_photo_file_id']:
            await callback.message.answer_photo(
                photo=profile['profile_photo_file_id'],
                caption=profile_text[:1024],
                parse_mode="HTML",
                reply_markup=profile_actions_keyboard(provider_id)
            )
        else:
            await callback.message.answer(
                profile_text,
                parse_mode="HTML",
                reply_markup=profile_actions_keyboard(provider_id)
            )