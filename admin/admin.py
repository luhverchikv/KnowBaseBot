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
• 🗄️ Экспорт/импорт базы знаний
• 🧹 Очистка кэша и логов

Выберите действие ниже или введите команду:
• /admin_stats — подробная статистика
• /admin_users — список пользователей
• /admin_config — настройка параметров
"""

def admin_keyboard():
    """Собирает inline-клавиатуру админ-панели."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
    )
    kb.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_config"),
        InlineKeyboardButton(text="🗄️ База данных", callback_data="admin_db")
    )
    kb.row(InlineKeyboardButton(text="🔙 В бот", callback_data="admin_back"))
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

@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery, is_owner: bool):
    """Возврат из админ-панели (заглушка — можно доработать)."""
    await call.answer()
    await call.message.answer("🔙 Вы вышли из панели администратора.")

