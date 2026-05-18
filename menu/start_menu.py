# menu/start_menu.py
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from logic.manage.db import Database

router = Router()
db = Database()

def start_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📂 Управление базой"),
        KeyboardButton(text="🎓 Викторина")
    )
    builder.row(
        KeyboardButton(text="📊 Анализ"),
        KeyboardButton(text="⚙️ Настройки")
    )
    return builder.as_markup(resize_keyboard=True)

def difficulty_keyboard():
    """Инлайн-клавиатура для выбора сложности (только для новых пользователей)."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="😊 Легкий", callback_data="diff_easy"),
        InlineKeyboardButton(text="🤔 Средний", callback_data="diff_medium"),
        InlineKeyboardButton(text="😈 Сложный", callback_data="diff_hard")
    )
    return kb.as_markup()

start_text = """
👋 <b>Добро пожаловать!</b>

Я помогу вам эффективно работать с базой знаний, проходить викторины и анализировать результаты.
📂 <b>Управление базой</b> – загрузка и обработка файлов
🎓 <b>Викторина</b> – проверка знаний по вашим материалам
📊 <b>Анализ</b> – статистика и разбор ответов
💬 <b>Обратная связь</b> – ваши предложения и поддержка

Выберите нужный раздел в меню ниже:
"""

@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.delete()
    user_id = message.from_user.id
    user_dir = Path("database") / str(user_id)
    
    is_new = not await asyncio.to_thread(db.user_exists, user_id)
    if is_new:
        await asyncio.to_thread(db.add_user, user_id)
        await asyncio.to_thread(user_dir.mkdir, parents=True, exist_ok=True)
        
        # ✅ Для нового пользователя сначала просим выбрать сложность
        await message.answer(
            "🎯 <b>Добро пожаловать!</b>\n\n"
            "Прежде чем начать, выберите уровень сложности вопросов для викторины:",
            reply_markup=difficulty_keyboard(),
            parse_mode="HTML"
        )
        return

    # ✅ Для существующего пользователя сразу показываем меню
    await asyncio.to_thread(user_dir.mkdir, parents=True, exist_ok=True)
    await message.answer(
        text=start_text,
        reply_markup=start_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("diff_"))
async def handle_difficulty_selection(call: CallbackQuery):
    """Обработчик выбора сложности."""
    await call.answer()
    user_id = call.from_user.id
    difficulty = call.data.split("_")[1]  # easy, medium, hard
    
    await asyncio.to_thread(db.set_user_difficulty, user_id, difficulty)
    
    diff_names = {"easy": "😊 Легкий", "medium": "🤔 Средний", "hard": "😈 Сложный"}
    selected_name = diff_names.get(difficulty, difficulty)
    
    await call.message.edit_text(
        f"✅ Выбран уровень: <b>{selected_name}</b>\n\n"
        "Приятного использования!",
        parse_mode="HTML"
    )
    
    # После выбора сложности показываем основное меню
    await call.message.answer(
        text=start_text,
        reply_markup=start_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == '/help')
async def user_help_handler(message: Message):
    await message.delete()
    await message.answer(
        "Мы на связи для вас!\n\n"
        "Если у вас есть замечание или идея для улучшения рабочих процессов, а может просто хотите поделиться своим мнением — напишите нам.\n"
        "Спасибо, что помогаете нам становиться лучше! ❤️\n\n"
    )


@router.callback_query(F.data == "close_callback")
async def close_callback_handler(call: CallbackQuery):
    await call.message.delete()
