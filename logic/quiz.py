# logic/quiz.py
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from logic.manage.db import Database
from logic.ai_connector import generate_quiz_question, evaluate_answer
from utils.logger import logger

router = Router()
db = Database()

class QuizStates(StatesGroup):
    waiting_answer = State()
    waiting_rating = State()

def quiz_menu_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎲 Сгенерировать вопрос", callback_data="quiz_generate"))
    return kb.as_markup()

@router.message(F.text == "Викторина")
async def quiz_menu(message: Message):
    await message.answer(
        "🧠 <b>Викторина</b>\n\n"
        "Нажмите кнопку ниже, чтобы получить случайный вопрос по вашей базе знаний.\n"
        "Лимит: 3 вопроса в день.",
        reply_markup=quiz_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "quiz_generate")
async def handle_generate(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user_id = call.from_user.id

    max_q = await asyncio.to_thread(db.get_max_questions_per_day, user_id)
    current_q = await asyncio.to_thread(db.get_daily_questions_count, user_id)
    if current_q >= max_q:
        await call.message.answer(f"❌ Дневной лимит исчерпан ({max_q}/{max_q}). Возвращайтесь завтра!")
        return

    filename = await asyncio.to_thread(db.get_random_user_file, user_id)
    if not filename:
        await call.message.answer("📂 База знаний пуста. Загрузите .md файлы через «Управление базой».")
        return

    file_path = Path("database") / str(user_id) / filename
    try:
        md_text = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {filename}: {e}")
        await call.message.answer("❌ Ошибка чтения файла.")
        return

    await call.message.answer("⏳ Генерирую вопрос по вашему файлу...")
    try:
        qa = await generate_quiz_question(md_text)
        question = qa.get("question", "Вопрос не сгенерирован.")
        correct_answer = qa.get("correct_answer", "Нет ответа.")

        q_id = await asyncio.to_thread(
            db.add_quiz_question,
            user_id=user_id, source_file=filename,
            question=question, correct_answer=correct_answer
        )

        await state.update_data(question_id=q_id, correct_answer=correct_answer, question_text=question)
        await state.set_state(QuizStates.waiting_answer)

        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="quiz_cancel"))
        await call.message.answer(
            f"❓ <b>Вопрос:</b>\n{question}\n\n Напишите ваш ответ:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        await call.message.answer("❌ Ошибка генерации вопроса. Проверьте API ключ или попробуйте позже.")

@router.message(QuizStates.waiting_answer)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("question_id")
    correct = data.get("correct_answer", "")
    question = data.get("question_text", "")

    await message.answer("⏳ Оцениваю ваш ответ...")
    try:
        eval_res = await evaluate_answer(question, correct, message.text)
        correctness = eval_res.get("correctness", "неправильно")
        feedback = eval_res.get("feedback", "Оценка завершена.")
        rating = eval_res.get("rating", 3)

        await asyncio.to_thread(db.update_quiz_result, q_id, message.text, correctness, feedback)
        await asyncio.to_thread(db.update_quiz_rating, q_id, rating)
        await state.set_state(QuizStates.waiting_rating)

        kb = InlineKeyboardBuilder()
        for r in range(1, 6):
            kb.row(InlineKeyboardButton(text=f"{r} ⭐", callback_data=f"quiz_rate:{r}"))
        kb.row(InlineKeyboardButton(text="🔙 В меню викторины", callback_data="quiz_menu"))

        emoji = "✅" if correctness == "правильно" else ("🔶" if correctness == "частично" else "❌")
        await message.answer(
            f"{emoji} <b>Результат:</b> {correctness}\n\n"
            f"💬 <b>Пояснение:</b> {feedback}\n\n"
            f"📝 Ваш ответ: <i>{message.text}</i>\n"
            f"✅ Правильный: <i>{correct}</i>\n\n"
            "Оцените сложность/качество вопроса (1-5):",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        await message.answer("❌ Ошибка оценки ответа.")
        await state.clear()

@router.callback_query(F.data.startswith("quiz_rate:"))
async def handle_rating(call: CallbackQuery, state: FSMContext):
    await call.answer()
    rating = int(call.data.split(":")[1])
    data = await state.get_data()
    q_id = data.get("question_id")

    if q_id:
        await asyncio.to_thread(db.update_quiz_rating, q_id, rating)

    await state.clear()
    await call.message.answer(
        "✅ Спасибо за оценку! Вопрос сохранён в историю.\nХотите попробовать ещё?",
        reply_markup=quiz_menu_keyboard()
    )

@router.callback_query(F.data == "quiz_cancel")
async def cancel_quiz(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.answer("🔙 Викторина отменена.", reply_markup=quiz_menu_keyboard())

@router.callback_query(F.data == "quiz_menu")
async def back_to_quiz_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.edit_text(
        "🧠 <b>Викторина</b>\n\nНажмите кнопку ниже, чтобы получить случайный вопрос...",
        reply_markup=quiz_menu_keyboard(),
        parse_mode="HTML"
    )

