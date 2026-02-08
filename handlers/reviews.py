"""
handlers/reviews.py
===================
Система оценки мастеров клиентами после завершения услуг
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from FSMstates import ReviewStates
from database import (
    create_provider_review,
    get_provider_rating_summary
)
from keyboards import (
    rating_keyboard,
    cancel_inline_keyboard,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("review_"))
async def handle_review_request(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса на оценку после завершения услуги"""
    await callback.answer()
    
    # Извлекаем данные из callback_data: review_{record_id}_{provider_id}
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.message.edit_text("❌ Неверный формат запроса.")
        return
    
    try:
        service_record_id = int(parts[1])
        provider_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка обработки данных.")
        return
    
    # Сохраняем данные для отзыва
    await state.update_data(
        review_provider_id=provider_id,
        review_service_record_id=service_record_id
    )
    
    # Запрашиваем оценку
    await callback.message.answer(
        "⭐ Оцените мастера (1-5 звёзд):\n"
        "Чем выше оценка, тем лучше качество услуги.",
        reply_markup=rating_keyboard()
    )
    await state.set_state(ReviewStates.waiting_for_rating)


@router.message(ReviewStates.waiting_for_rating)
async def process_rating(message: Message, state: FSMContext):
    """Обработка выбора оценки"""
    if message.text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="client")
        return
    
    # Преобразуем звёзды в число
    rating_map = {
        "⭐": 1,
        "⭐⭐": 2,
        "⭐⭐⭐": 3,
        "⭐⭐⭐⭐": 4,
        "⭐⭐⭐⭐⭐": 5
    }
    
    rating = rating_map.get(message.text)
    if not rating:
        await message.answer(
            "Выберите оценку кнопками ниже:",
            reply_markup=rating_keyboard()
        )
        return
    
    # Сохраняем оценку
    await state.update_data(review_rating=rating)
    
    # Запрашиваем комментарий
    await message.answer(
        "Напишите комментарий к оценке (или '-' если без комментария):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Пропустить", callback_data="skip_comment")]
        ])
    )
    await state.set_state(ReviewStates.waiting_for_comment)


@router.callback_query(F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    """Пропуск комментария"""
    await callback.answer()
    # Используем '-' как сигнал пропуска комментария
    await process_comment(callback.message, state, "-")


@router.message(ReviewStates.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext, comment_text: str = None):
    """Обработка комментария и сохранение отзыва"""
    if comment_text is None:
        comment_text = message.text
    
    if comment_text == "В меню":
        await state.clear()
        from handlers.logout import return_to_role_menu
        await return_to_role_menu(message, state, role="client")
        return
    
    # Получаем данные отзыва
    data = await state.get_data()
    provider_id = data['review_provider_id']
    service_record_id = data['review_service_record_id']
    rating = data['review_rating']
    comment = None if comment_text.strip() == '-' else comment_text.strip()
    
    # Сохраняем отзыв
    await create_provider_review(
        provider_id=provider_id,
        client_id=message.from_user.id,
        service_record_id=service_record_id,
        rating=rating,
        comment=comment
    )
    
    # Получаем обновлённую статистику мастера
    stats = await get_provider_rating_summary(provider_id)
    
    # Формируем сообщение с благодарностью
    thanks_msg = (
        f"✅ Спасибо за отзыв!\n"
        f"Ваша оценка: {'⭐' * rating}\n"
    )
    if comment and comment != '-':
        thanks_msg += f"Комментарий: {comment[:50]}...\n\n"
    
    thanks_msg += (
        f"Статистика мастера обновлена:\n"
        f"Средняя оценка: {stats['average_rating']:.1f} ⭐\n"
        f"Отзывов: {stats['review_count']}\n"
        f"Клиентов: {stats['client_base']}"
    )
    
    await message.answer(
        thanks_msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="review_menu")]
        ])
    )
    await state.clear()


@router.callback_query(F.data == "review_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню клиента"""
    await callback.answer()
    from handlers.logout import return_to_role_menu
    await return_to_role_menu(callback.message, state, role="client")