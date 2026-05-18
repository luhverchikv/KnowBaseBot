# logic/feedback.py
import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from logic.manage.db import Database
from utils.logger import logger

router = Router()
db = Database()

# ===================== FSM STATES =====================
class FeedbackStates(StatesGroup):
    waiting_feedback = State()  # Ожидание текста отзыва

# ===================== КЛАВИАТУРЫ =====================
def feedback_cancel_keyboard():
    """Кнопка отмены ввода отзыва."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="feedback_cancel"))
    return kb.as_markup()

# ===================== HANDLERS =====================
@router.message(F.text == "💬 Обратная связь")
async def feedback_start(message: Message, state: FSMContext):
    """Точка входа: пользователь нажал кнопку «Обратная связь»."""
    await state.set_state(FeedbackStates.waiting_feedback)
    
    text = (
        "💬 <b>Обратная связь</b>\n\n"
        "Разработчики очень рады, что вы используете это приложение! 🎉\n\n"
        "Мы ценим ваше мнение и с нетерпением ждём отзывы и предложения по улучшению бота.\n\n"
        "Напишите, что вам нравится, а что можно сделать лучше — каждое сообщение будет прочитано! ✨\n\n"
        "<i>Или нажмите «Отмена», чтобы вернуться в меню.</i>"
    )
    
    await message.answer(text, reply_markup=feedback_cancel_keyboard(), parse_mode="HTML")
    await message.delete()

@router.callback_query(F.data == "feedback_cancel", FeedbackStates.waiting_feedback)
async def feedback_cancel(call: CallbackQuery, state: FSMContext):
    """Отмена ввода отзыва."""
    await call.answer()
    await state.clear()
    await call.message.edit_text("✏️ Ввод отзыва отменён. Возвращаемся в меню.")


# logic/feedback.py (внутри feedback_received)

@router.message(FeedbackStates.waiting_feedback)
async def feedback_received(message: Message, state: FSMContext):
    """Получение текста отзыва от пользователя."""
    feedback_text = message.text.strip()
    
    if len(feedback_text) < 5:
        await message.answer("⚠️ Отзыв слишком короткий. Пожалуйста, напишите подробнее (минимум 5 символов).")
        return
    
    user_id = message.from_user.id
    
    # ✅ Сохраняем в БД
    await asyncio.to_thread(db.save_feedback, user_id, feedback_text)
    
    # Логируем (опционально)
    logger.info(f"Feedback saved from user {user_id}: {feedback_text[:100]}...")
    
    # ✅ Отправляем подтверждение
    await message.answer(
        "✅ <b>Спасибо за ваш отзыв!</b>\n\n"
        "Ваше сообщение успешно отправлено разработчикам.\n"
        "Мы обязательно его изучим и учтём при улучшении бота. 💙\n\n"
        "Если у вас появятся ещё идеи — пишите в любое время!",
        parse_mode="HTML"
    )
    
    await state.clear()
