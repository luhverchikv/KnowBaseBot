# menu/start_menu.py
import asyncio
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from logic.manager.db import Database
from aiogram.utils.keyboard import InlineKeyboardBuilder


router = Router()
db = Database()



def start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data="set_feedback")],
        ]
    )

start_text = """Привет!"""

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
