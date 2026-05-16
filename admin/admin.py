# admin/admin.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.filter import is_owner

router = Router()

# Текст приветствия администратора
ADMIN_WELCOME = """
🔐 <b>Панель администратора</b>

Добро пожаловать, владелец бота!

🛠 <b>Доступные функции:</b>
• 📊 Статистика по пользователям
• ⚙️ Управление лимитами
• 🧹 Очистка логов

Выберите действие ниже или введите команду:
"""

def admin_keyboard():
    """Собирает inline-клавиатуру админ-панели."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_config"),
        InlineKeyboardButton(text="🔙 В бот", callback_data="admin_close"),
    )
    return kb.as_markup()

@router.message(Command("admin"), is_owner)
async def admin_panel(message: Message):
    """Точка входа в админ-панель (только для owner_id)."""
    await message.answer(
        text=ADMIN_WELCOME,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

@router.message(Command("admin"), ~is_owner)
async def admin_denied(message: Message):
    """Обработка попытки доступа не-владельца к /admin."""
    await message.answer("🔒 Доступ запрещён. Эта команда доступна только владельцу бота.")

@router.callback_query(F.data == "admin_close", is_owner)
async def admin_back(call: CallbackQuery):
    await call.answer()
    await call.message.delete()

