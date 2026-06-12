# logic/quiz.py

import os
import asyncio
from pathlib import Path
import aiofiles
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from voice_engine.converter import ogg_to_wav
from voice_engine.recognizer import recognize_text_from_wav
from logic.ai_connector import ai_client
from utils.logger import logger

from database.requests import (
    get_user_files,
    get_user_difficulty,
    add_quiz_question,
    update_quiz_result,
    get_unanswered_quiz_question,
    get_unanswered_questions_count,
    add_quiz_questions_batch,
    get_file_by_id,
    # ✅ VIP: Функции для проверки и учёта генераций пулов
    get_daily_pool_generations,
    get_generation_limit,
    increment_pool_generation,
)

router = Router()

class QuizStates(StatesGroup):
    waiting_answer = State()


def quiz_menu_keyboard(unanswered_count: int = 0) -> InlineKeyboardMarkup:
    """
    Собирает клавиатуру меню викторины с счётчиком пропущенных вопросов.
    :param unanswered_count: количество неотвеченных вопросов
    """
    # Формируем текст кнопки со счётчиком
    if unanswered_count > 0:
        resume_text = f"📝 Ответить на пропущенный ({unanswered_count})"
    else:
        resume_text = "📝 Ответить на пропущенный"
    
    return InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="🎲 Сгенерировать вопросы", callback_data="quiz_generate_pool")
    ).row(
        InlineKeyboardButton(text=resume_text, callback_data="quiz_resume")
    ).as_markup()
    

@router.message(F.text == "🎓 Викторина")
async def quiz_menu(message: Message):
    user_id = message.from_user.id
    unanswered_count = await get_unanswered_questions_count(user_id)
    # ✅ VIP: Получаем лимит генераций пулов с учётом статуса подписки
    current_gens = await get_daily_pool_generations(user_id)
    limit = await get_generation_limit(user_id)

    await message.answer(
        "🧠 <b>Викторина</b>\n\n"
        "Нажмите кнопку, чтобы сгенерировать пул вопросов по выбранному файлу.\n"
        f"🎲 Генераций сегодня: <b>{current_gens}/{limit}</b>\n\n"
        f"💡 Free пользователям — 2 генерации/день, VIP — до 10.",
        reply_markup=quiz_menu_keyboard(unanswered_count),
        parse_mode="HTML"
    )
    try:
        await message.delete()
    except Exception:
        pass

# ✅ НОВЫЙ ОБРАБОТЧИК: Показ списка файлов для генерации пула
@router.callback_query(F.data == "quiz_generate_pool")
async def handle_generate_pool_menu(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id

    # ✅ VIP: Проверяем лимит генераций пулов (Free: 2, VIP: 10)
    current_gens = await get_daily_pool_generations(user_id)
    limit = await get_generation_limit(user_id)

    if current_gens >= limit:
        upgrade_text = (
            "\n\n💡 Хотите больше генераций? Оформите VIP-подписку — до 10 в день!"
            if limit == 2 else ""
        )
        await call.message.answer(
            f"❌ Лимит генераций пулов ({current_gens}/{limit}) на сегодня исчерпан.{upgrade_text}\n\n"
            "Или нажмите <b>«📝 Ответить на пропущенный»</b> — это не требует генерации.",
            parse_mode="HTML",
            reply_markup=quiz_menu_keyboard()
        )
        return

    # Получаем список файлов пользователя
    user_files = await get_user_files(user_id)
    if not user_files:
        await call.message.answer(
            "📂 Ваша база знаний пуста. Сначала загрузите .md файлы через управление базой."
        )
        return

    # Строим клавиатуру со списком файлов
    kb = InlineKeyboardBuilder()
    for f in user_files:
        # Обрезаем длинные имена файлов для красоты
        display_name = f.filename if len(f.filename) <= 30 else f.filename[:27] + "..."
        kb.row(InlineKeyboardButton(text=f"📄 {display_name}", callback_data=f"quiz_select_file:{f.id}"))

    kb.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="quiz_cancel_pool"))

    await call.message.answer(
        f"📚 <b>Выберите файл</b> для генерации пула вопросов:\n\n"
        f"🎲 Осталось генераций: <b>{limit - current_gens}</b>\n\n"
        "По выбранному файлу будет сгенерировано 10 вопросов за один запрос к ИИ.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# ✅ НОВЫЙ ОБРАБОТЧИК: Отмена выбора файла
@router.callback_query(F.data == "quiz_cancel_pool")
async def cancel_pool_generation(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "❌ Генерация вопросов отменена.",
        reply_markup=quiz_menu_keyboard()
    )

# ✅ НОВЫЙ ОБРАБОТЧИК: Выбор файла и генерация пула
@router.callback_query(F.data.startswith("quiz_select_file:"))
async def handle_file_selection_and_generate(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id

    try:
        file_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.message.answer("❌ Ошибка: некорректный ID файла.")
        return

    # ✅ VIP: Дополнительная проверка лимита генераций (защита от race conditions)
    current_gens = await get_daily_pool_generations(user_id)
    limit = await get_generation_limit(user_id)

    if current_gens >= limit:
        await call.message.answer(
            f"❌ Лимит генераций ({current_gens}/{limit}) исчерпан.",
            reply_markup=quiz_menu_keyboard()
        )
        return

    # Получаем данные файла
    file_data = await get_file_by_id(file_id)
    if not file_data:
        await call.message.answer("❌ Ошибка: файл не найден.")
        return

    file_path = Path(file_data.file_path)

    # Читаем файл
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
            md_text = await f.read()
    except Exception as e:
        logger.error(f"Read fail for quiz pool generation {file_path}: {e}")
        await call.message.answer("❌ Ошибка чтения файла.")
        return

    if len(md_text.strip()) < 500:
        await call.message.answer(
            "⚠️ Файл слишком короткий для генерации качественных вопросов. "
            "Выберите другой файл или дополните этот."
        )
        return

    # Показываем статус
    status_msg = await call.message.answer(
        "⏳ <i>Нейросеть анализирует файл и генерирует пул из 10 вопросов... Это может занять 10-20 секунд.</i>",
        parse_mode="HTML"
    )

    # Получаем сложность пользователя
    difficulty = await get_user_difficulty(user_id)

    # Генерируем пул вопросов
    success, pool, err, token_usage = await ai_client.generate_quiz_pool(md_text, difficulty=difficulty, count=10)

    try:
        await status_msg.delete()
    except Exception:
        pass

    if not success:
        await call.message.answer(f"❌ Ошибка генерации пула ИИ: {err}")
        return

    # Сохраняем пул в БД
    total_tokens = token_usage.total_tokens if token_usage else 0
    saved_count = await add_quiz_questions_batch(
        user_id=user_id,
        source_file=file_data.filename,
        questions_data=pool,
        total_gen_tokens=total_tokens
    )

    # ✅ VIP: Увеличиваем счётчик генераций пулов
    await increment_pool_generation(user_id)
    logger.info(f"✅ Pool generation logged for user {user_id}. Total today: {current_gens + 1}/{limit}")

    # Получаем обновлённые данные для отображения
    new_gens = await get_daily_pool_generations(user_id)

    # Успешное уведомление
    await call.message.answer(
        f"✅ <b>Пул успешно создан!</b>\n\n"
        f"📄 Файл: <code>{file_data.filename}</code>\n"
        f"❓ Сгенерировано вопросов: <b>{saved_count}</b>\n"
        f"🪙 Потрачено токенов (всего): <b>{total_tokens}</b>\n\n"
        f"🎲 Генераций сегодня: <b>{new_gens}/{limit}</b>\n\n"
        f"Теперь нажмите <b>«📝 Ответить на пропущенный»</b>, чтобы начать проходить вопросы!",
        parse_mode="HTML",
        reply_markup=quiz_menu_keyboard()
    )

# ✅ ОБРАБОТЧИК ДЛЯ ПРОПУЩЕННЫХ ВОПРОСОВ (остается без изменений)
@router.callback_query(F.data == "quiz_resume")
async def handle_resume_quiz(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user_id = call.from_user.id
    
    unanswered_q = await get_unanswered_quiz_question(user_id)
    
    if not unanswered_q:
        await call.message.answer(
            "🎉 У вас нет пропущенных вопросов! Отличная работа, так держать.",
            reply_markup=quiz_menu_keyboard()
        )
        return
    
    await state.update_data(
        question_id=unanswered_q.id,
        correct_answer=unanswered_q.correct_answer,
        question_text=unanswered_q.question,
        source_file=unanswered_q.source_file
    )
    await state.set_state(QuizStates.waiting_answer)
    
    display_filename = unanswered_q.source_file if len(unanswered_q.source_file) <= 30 else unanswered_q.source_file[:27] + "..."
    
    kb = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="🔙 Отмена", callback_data="quiz_cancel")
    )
    
    await call.message.answer(
        f"📄 <i>Источник: {display_filename}</i>\n\n"
        f"❓ <b>Вопрос:</b>\n{unanswered_q.question}\n\n"
        f"Напишите ответ (текстом или голосом):",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# ✅ ОБРАБОТЧИК ОТВЕТА (остается без изменений)
@router.message(QuizStates.waiting_answer, F.text | F.voice)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("question_id")
    correct = data.get("correct_answer", "")
    question = data.get("question_text", "")
    
    user_answer = ""
    unanswered_count = await get_unanswered_questions_count(message.from_user.id)
    # Обработка голосового ответа
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
    
    elif message.text:
        user_answer = message.text.strip()
        if not user_answer:
            return
    else:
        return
    
    # Оценка ответа через ИИ
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
    
    await update_quiz_result(
        q_id=q_id,
        user_answer=user_answer,
        correctness=correctness,
        feedback=feedback,
        rating=rating,
        eval_tokens=eval_tokens
    )
    
    await state.clear()
    
    emoji = {"правильно": "✅", "частично": "🔶", "неправильно": "❌"}.get(correctness, "❓")
    stars = "⭐" * rating + "☆" * (5 - rating)
    
    await message.answer(
        f"{emoji} <b>Результат:</b> {correctness}\n"
        f"{stars} <b>Балл:</b> {rating}/5\n\n"
        f"💬 <b>Пояснение ИИ:</b>\n{feedback}\n\n"
        f"📝 <b>Ваш ответ:</b>\n<i>{user_answer}</i>\n\n"
        f"✅ <b>Правильный ответ:</b>\n<i>{correct}</i>",
        reply_markup=quiz_menu_keyboard(unanswered_count),
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
