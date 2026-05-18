# logic/quiz.py
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from logic.manage.db import Database
from logic.ai_connector import ai_client
from utils.logger import logger

router = Router()
db = Database()

class QuizStates(StatesGroup):
    waiting_answer = State()  # ✅ Оставляем только одно состояние

def quiz_menu_keyboard():
    return InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="🎲 Сгенерировать вопрос", callback_data="quiz_generate")
    ).as_markup()

@router.message(F.text == "🎓 Викторина")
async def quiz_menu(message: Message):
    await message.answer(
        "🧠 <b>Викторина</b>\n\n"
        "Нажмите кнопку, чтобы получить вопрос по вашей базе.\n"
        "Лимит: 3 в день.",
        reply_markup=quiz_menu_keyboard(),
        parse_mode="HTML"
    )
    await message.delete()


@router.callback_query(F.data == "quiz_generate")
async def handle_generate(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user_id = call.from_user.id
    
    max_q = await asyncio.to_thread(db.get_max_questions_per_day, user_id)
    if await asyncio.to_thread(db.get_daily_questions_count, user_id) >= max_q:
        await call.message.answer(f"❌ Лимит ({max_q}) исчерпан. Возвращайтесь завтра!")
        return

    filename = await asyncio.to_thread(db.get_random_user_file, user_id)
    if not filename:
        await call.message.edit_text("📂 База пуста. Загрузите .md файлы.")
        return

    file_path = Path("database") / str(user_id) / filename
    try:
        md_text = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
    except Exception as e:
        logger.error(f"Read fail: {e}")
        await call.message.edit_text("❌ Ошибка чтения файла.")
        return

    await call.message.answer("⏳ Генерирую вопрос...")
    difficulty = await asyncio.to_thread(db.get_user_difficulty, user_id)
    
    success, qa, err, gen_tokens = await ai_client.generate_quiz_question(md_text, difficulty)
    if not success:
        await call.message.edit_text(f"❌ AI ошибка: {err}")
        return

    # ✅ ИСПРАВЛЕНО: передаём gen_tokens
    q_id = await asyncio.to_thread(
        db.add_quiz_question,
        user_id, filename,
        qa.get("question", "?"), qa.get("correct_answer", "?"),
        gen_tokens=gen_tokens
    )
    
    await state.update_data(
        question_id=q_id,
        correct_answer=qa.get("correct_answer", ""),
        question_text=qa.get("question", "")
    )
    await state.set_state(QuizStates.waiting_answer)
    
    kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🔙 Отмена", callback_data="quiz_cancel"))
    await call.message.answer(
        f"❓ <b>Вопрос:</b>\n{qa.get('question', '?')}\n\nНапишите ответ:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.message(QuizStates.waiting_answer)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("question_id")
    correct = data.get("correct_answer", "")
    question = data.get("question_text", "")
    user_answer = message.text

    await message.answer("⏳ ИИ оценивает ваш ответ...")
    
    # ✅ ИСПРАВЛЕНО: распаковываем 4 значения
    success, res, err, eval_tokens = await ai_client.evaluate_answer(question, correct, user_answer)
    if not success:
        await message.answer(f"❌ Оценка не удалась: {err}")
        await state.clear()
        return

    correctness = res.get("correctness", "неправильно")
    feedback = res.get("feedback", "Оценка завершена.")
    rating = res.get("rating", 3)

    # ✅ ИСПРАВЛЕНО: сохраняем токены оценки
    if eval_tokens:
        await asyncio.to_thread(db.update_eval_tokens, q_id, eval_tokens)

    await asyncio.to_thread(db.update_quiz_result, q_id, user_answer, correctness, feedback)
    await asyncio.to_thread(db.update_quiz_rating, q_id, rating)
    await state.clear()

    emoji = {"правильно": "✅", "частично": "🔶", "неправильно": "❌"}.get(correctness, "❓")
    stars = "⭐" * rating + "☆" * (5 - rating)
    
    await message.answer(
        f"{emoji} <b>Результат:</b> {correctness}\n"
        f"{stars} <b>Балл:</b> {rating}/5\n\n"
        f"💬 <b>Пояснение ИИ:</b>\n{feedback}\n\n"
        f"📝 <b>Ваш ответ:</b>\n<i>{user_answer}</i>\n\n"
        f"✅ <b>Правильный ответ:</b>\n<i>{correct}</i>",
        reply_markup=quiz_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "quiz_cancel")
async def cancel_quiz(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.answer(
        "🔙 Викторина отменена.",
        reply_markup=quiz_menu_keyboard()
    )

