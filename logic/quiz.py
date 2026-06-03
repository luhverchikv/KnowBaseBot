# logic/quiz.py
import os
import asyncio
from pathlib import Path
import aiofiles  # Для асинхронного неблокирующего чтения файлов
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импортируем зависимости проекта
from voice_engine.converter import ogg_to_wav
from voice_engine.recognizer import recognize_text_from_wav
from logic.ai_connector import ai_client
from utils.logger import logger

# Подключаем асинхронные ORM запросы вместо старого класса Database
from database.requests import (
    get_user_max_questions_per_day,
    get_daily_questions_count,
    get_user_files,
    get_user_difficulty,
    add_quiz_question,
    update_quiz_result
)

router = Router()

class QuizStates(StatesGroup):
    waiting_answer = State()

def quiz_menu_keyboard():
    return InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="🎲 Сгенерировать вопрос", callback_data="quiz_generate")
    ).as_markup()

@router.message(F.text == "🎓 Викторина")
async def quiz_menu(message: Message):
    user_id = message.from_user.id
    
    # Получаем лимит через ORM
    max_questions = await get_user_max_questions_per_day(user_id)
    
    await message.answer(
        "🧠 <b>Викторина</b>\n\n"
        "Нажмите кнопку, чтобы получить вопрос по вашей базе.\n"
        f"Лимит: <b>{max_questions}</b> в день.",
        reply_markup=quiz_menu_keyboard(),
        parse_mode="HTML"
    )
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "quiz_generate")
async def handle_generate(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user_id = call.from_user.id
    
    # 1. Проверяем суточный лимит вопросов
    max_q = await get_user_max_questions_per_day(user_id)
    current_q_count = await get_daily_questions_count(user_id)
    
    if current_q_count >= max_q:
        await call.message.answer(f"❌ Лимит ({max_q}) на сегодня исчерпан. Возвращайтесь завтра!")
        return

    # 2. Выбираем случайный файл из базы данных пользователя
    user_files = await get_user_files(user_id)
    if not user_files:
        await call.message.edit_text("📂 Ваша база знаний пуста. Сначала загрузите .md файлы через управление базой.")
        return
    
    selected_file = random.choice(user_files)
    filename = selected_file.filename
    file_path = Path(selected_file.file_path)

    # 3. Асинхронно читаем контент markdown-файла
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
            md_text = await f.read()
    except Exception as e:
        logger.error(f"Read fail for file {file_path}: {e}")
        await call.message.edit_text("❌ Ошибка чтения файла базы знаний.")
        return

    status_msg = await call.message.answer("⏳ <i>Нейросеть изучает материал и генерирует вопрос... Пожалуйста, подождите.</i>", parse_mode="HTML")
    
    # 4. Запрашиваем у ИИ генерацию вопроса с учетом сложности пользователя
    difficulty = await get_user_difficulty(user_id)
    success, qa, err, gen_tokens = await ai_client.generate_quiz_question(md_text, difficulty)
    
    try:
        await status_msg.delete()
    except Exception:
        pass

    if not success:
        await call.message.answer(f"❌ Ошибка генерации ИИ: {err}")
        return

    # 5. Сохраняем сгенерированный вопрос в БД через ORM
    q_id = await add_quiz_question(
        user_id=user_id,
        source_file=filename,
        question=qa.get("question", "?"),
        correct_answer=qa.get("correct_answer", "?"),
        gen_tokens=gen_tokens
    )
    
    # Сохраняем состояние контекста
    await state.update_data(
        question_id=q_id,
        correct_answer=qa.get("correct_answer", ""),
        question_text=qa.get("question", ""),
        source_file=filename
    )
    await state.set_state(QuizStates.waiting_answer)
    
    # Безопасное отображение длинных имен файлов
    display_filename = filename if len(filename) <= 30 else filename[:27] + "..."
    
    kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🔙 Отмена", callback_data="quiz_cancel"))
    await call.message.answer(
        f"📄 <i>Источник: {display_filename}</i>\n"
        f"💡 <i>Описание темы: {selected_file.description or 'Не указано'}</i>\n\n" # Добавили вывод описания ИИ!
        f"❓ <b>Вопрос:</b>\n{qa.get('question', '?')}\n\nНапишите ответ (текстом или голосом):",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    

@router.message(QuizStates.waiting_answer, F.text | F.voice)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("question_id")
    correct = data.get("correct_answer", "")
    question = data.get("question_text", "")

    user_answer = ""

    # 🎙️ Обработка голосового ответа
    if message.voice:
        if message.voice.duration > 60:
            await message.answer("⚠️ Голосовое сообщение слишком длинное (максимум 60 сек). Отправьте покороче или напишите текстом.")
            return

        status_voice = await message.answer("⏳ Распознаю вашу речь...")

        file = await message.bot.get_file(message.voice.file_id)
        ogg_path = f"temp_voice_{message.from_user.id}_{q_id}.ogg"
        wav_path = f"temp_voice_{message.from_user.id}_{q_id}.wav"

        await message.bot.download_file(file.file_path, destination=ogg_path)
        await ogg_to_wav(ogg_path, wav_path)

        try:
            user_answer = recognize_text_from_wav(wav_path)
        except Exception as e:
            logger.error(f"Voice recognition failed: {e}")
            await message.answer("⚠️ Не удалось распознать аудио. Напишите ваш ответ текстом.")
            return
        finally:
            try:
                await status_voice.delete()
            except Exception:
                pass
            for p in (ogg_path, wav_path):
                if os.path.exists(p):
                    os.remove(p)

        if not user_answer or not user_answer.strip():
            await message.answer("⚠️ Аудиозапись пуста или слова не разобраны. Повторите попытку.")
            return

    # 📝 Обработка текстового ответа
    elif message.text:
        user_answer = message.text.strip()
        if not user_answer:
            return 
    else:
        return

    # 🤖 Оценка ответа через ИИ
    status_eval = await message.answer("⏳ Нейросеть оценивает ваш ответ...")
    success, res, err, eval_tokens = await ai_client.evaluate_answer(question, correct, user_answer)
    
    try:
        await status_eval.delete()
    except Exception:
        pass

    if not success:
        await message.answer(f"❌ Оценка не удалась: {err}")
        await state.clear()
        return

    correctness = res.get("correctness", "неправильно")
    feedback = res.get("feedback", "Оценка завершена.")
    rating = res.get("rating", 3)

    # ✅ Обновляем результаты викторины в БД одной чистой атомарной ORM транзицией
    await update_quiz_result(
        q_id=q_id,
        user_answer=user_answer,
        correctness=correctness,
        feedback=feedback,
        rating=rating,
        eval_tokens=eval_tokens
    )
    
    await state.clear()

    # Формируем красивый отчет
    emoji = {"правильно": "✅", "частично": "🔶", "неправильно": "❌"}._get(correctness, "❓")
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
