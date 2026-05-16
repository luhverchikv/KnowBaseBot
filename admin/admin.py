# admin/admin.py
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.filter import is_owner
from logic.manage.db import Database

router = Router()
db = Database()

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
    """Собирает inline-клавиатуру админ-панели (каждая кнопка в отдельном ряду)."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    kb.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_config"))
    kb.row(InlineKeyboardButton(text="🔙 Закрыть панель", callback_data="admin_close"))
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


@router.callback_query(F.data == "admin_stats", is_owner)
async def admin_stats_handler(call: CallbackQuery):
    """Обработчик кнопки «Статистика»."""
    await call.answer()
    
    # Асинхронные запросы к БД (не блокируем event loop)
    total_users = await asyncio.to_thread(db.get_total_users_count)
    today_qs = await asyncio.to_thread(db.get_questions_count_today)
    yesterday_qs = await asyncio.to_thread(db.get_questions_count_yesterday)

    text = (
        f"📊 <b>Общая статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"📅 Вопросов сгенерировано сегодня: <b>{today_qs}</b>\n"
        f" Вопросов сгенерировано вчера: <b>{yesterday_qs}</b>"
    )
    # Обновляем сообщение, сохраняя клавиатуру
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_close", is_owner)
async def admin_back(call: CallbackQuery):
    await call.answer()
    await call.message.delete()

@router.callback_query(F.data == "admin_tokens")
async def admin_tokens_handler(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id  # или агрегируйте по всем пользователям
    
    stats = await asyncio.to_thread(db.get_token_stats, user_id)
    text = (
        f"🪙 <b>Статистика токенов</b>\n\n"
        f"📝 Генерация вопросов: <b>{stats['generation']}</b>\n"
        f"✅ Оценка ответов: <b>{stats['evaluation']}</b>\n"
        f"📊 <b>Всего:</b> {stats['total']} токенов"
    )
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")

