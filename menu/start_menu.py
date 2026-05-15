# menu/start_menu.py
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message
from logic.manage.db import Database
from aiogram.utils.keyboard import ReplyKeyboardBuilder, KeyboardButton

router = Router()
db = Database()


def start_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Управление базой"),
        KeyboardButton(text="Викторина")
    )
    builder.row(
        KeyboardButton(text="Анализ"),
        KeyboardButton(text="Обратная связь")
    )
    # resize_keyboard=True делает клавиатуру компактной (по ширине экрана)
    return builder.as_markup(resize_keyboard=True)

start_text = """
👋 <b>Добро пожаловать!</b>

Я помогу вам эффективно работать с базой знаний, проходить викторины и анализировать результаты.
📂 <b>Управление базой</b> – загрузка и обработка файлов
🧠 <b>Викторина</b> – проверка знаний по вашим материалам
📊 <b>Анализ</b> – статистика и разбор ответов
💬 <b>Обратная связь</b> – ваши предложения и поддержка

Выберите нужный раздел в меню ниже:
"""


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.delete()
    user_id = message.from_user.id
    # 1. Работа с БД
    if not await asyncio.to_thread(db.user_exists, user_id):
        await asyncio.to_thread(db.add_user, user_id)

    # 2. Создание директории для файлов базы знаний пользователя
    user_dir = Path("database") / str(user_id)
    # parents=True: создаст папку database/, если её нет
    # exist_ok=True: не вызовет ошибку, если папка уже существует
    await asyncio.to_thread(user_dir.mkdir, parents=True, exist_ok=True)

    await message.answer(
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
