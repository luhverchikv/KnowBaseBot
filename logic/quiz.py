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
    waiting_answer = State()
    waiting_rating = State()

def quiz_menu_keyboard():
    return InlineKeyboardBuilder().row(InlineKeyboardButton(text="🎲 Сгенерировать вопрос", callback_data="quiz_generate")).as_markup()

@router.message(F.text == "Викторина")
async def quiz_menu(message: Message):
    await message.answer("🧠 <b>Викторина</b>\n\nНажмите кнопку, чтобы получить вопрос по вашей базе.\nЛимит: 3 в день.", reply_markup=quiz_menu_keyboard(), parse_mode="HTML")

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
        await call.message.answer("📂 База пуста. Загрузите .md файлы.")
        return

    file_path = Path("database") / str(user_id) / filename
    try:
        md_text = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
    except Exception as e:
        logger.error(f"Read fail: {e}")
        await call.message.answer("❌ Ошибка чтения файла.")
        return

    await call.message.answer("⏳ Генерирую вопрос...")
    success, qa, err = await ai_client.generate_quiz_question(md_text)
    if not success:
        await call.message.answer(f"❌ AI ошибка: {err}")
        return

    q_id = await asyncio.to_thread(db.add_quiz_question, user_id, filename, qa.get("question", "?"), qa.get("correct_answer", "?"))
    await state.update_data(question_id=q_id, correct_answer=qa.get("correct_answer", ""), question_text=qa.get("question", ""))
    await state.set_state(QuizStates.waiting_answer)
    
    kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🔙 Отмена", callback_data="quiz_cancel"))
    await call.message.answer(f"❓ <b>Вопрос:</b>\n{qa.get('question', '?')}\n\nНапишите ответ:", reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(QuizStates.waiting_answer)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id, correct, question = data.get("question_id"), data.get("correct_answer", ""), data.get("question_text", "")
    await message.answer(" Оцениваю...")
    
    success, res, err = await ai_client.evaluate_answer(question, correct, message.text)
    if not success:
        await message.answer(f"❌ Оценка не удалась: {err}")
        await state.clear()
        return

    correctness, feedback, rating = res.get("correctness", "неправильно"), res.get("feedback", ""), res.get("rating", 3)
    await asyncio.to_thread(db.update_quiz_result, q_id, message.text, correctness, feedback)
    await asyncio.to_thread(db.update_quiz_rating, q_id, rating)
    await state.set_state(QuizStates.waiting_rating)

    kb = InlineKeyboardBuilder()
    for r in range(1, 6): kb.row(InlineKeyboardButton(text=f"{r} ⭐", callback_data=f"quiz_rate:{r}"))
    kb.row(InlineKeyboardButton(text="🔙 В меню", callback_data="quiz_menu"))
    
    emoji = "✅" if correctness == "правильно" else ("🔶" if correctness == "частично" else "❌")
    await message.answer(f"{emoji} <b>{correctness}</b>\n {feedback}\n📝 Ваш: <i>{message.text}</i>\n✅ Верный: <i>{correct}</i>\n\nОцените вопрос (1-5):", reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("quiz_rate:"))
async def handle_rating(call: CallbackQuery, state: FSMContext):
    await call.answer()
    rating = int(call.data.split(":")[1])
    data = await state.get_data()
    if data.get("question_id"): await asyncio.to_thread(db.update_quiz_rating, data["question_id"], rating)
    await state.clear()
    await call.message.answer("✅ Спасибо! Хотите ещё?", reply_markup=quiz_menu_keyboard())

@router.callback_query(F.data == "quiz_cancel")
async def cancel_quiz(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.answer(" Отменено.", reply_markup=quiz_menu_keyboard())

@router.callback_query(F.data == "quiz_menu")
async def back_to_quiz_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.edit_text("🧠 <b>Викторина</b>\n\nНажмите кнопку ниже...", reply_markup=quiz_menu_keyboard(), parse_mode="HTML")

