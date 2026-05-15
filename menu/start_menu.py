# menu/start_menu.py

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

start_text = """
Привет!
"""

@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.delete()
    user_id = message.from_user.id
    #if not db.user_exists(user_id):
        #db.add_user(user_id) # внести пользователя в таблицу users
        # если не моздано, то создать директорию, где будут храниться файлы базы знаний
        # если не создано, то создать таблицу пользователя с вопросами

    await message.answer(
        text=start_text,
        reply_markup=start_keyboard(),
        parse_mode="HTML"
    )