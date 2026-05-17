# admin/admin.py
import asyncio
import math
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.filter import is_owner
from logic.manage.db import Database
from utils.pagination import build_pagination_keyboard

router = Router()
db = Database()
USERS_PER_PAGE = 10


# Текст приветствия администратора
ADMIN_WELCOME = """
🔐 <b>Панель администратора</b>

Добро пожаловать, владелец бота!

🛠 <b>Доступные функции:</b>
• 📊 Статистика по пользователям
• ⚙️ Управление лимитами
• 🧹 Чтение и очистка логов

Выберите действие ниже или введите команду:
"""

def admin_keyboard():
    """Собирает inline-клавиатуру админ-панели (каждая кнопка в отдельном ряду)."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    kb.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_config"))
    kb.row(InlineKeyboardButton(text="🪙 Токены за сутки", callback_data="admin_tokens_day"))
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
    await message.delete()


@router.message(Command("admin"), ~is_owner)
async def admin_denied(message: Message):
    """Обработка попытки доступа не-владельца к /admin."""
    await message.answer("🔒 Доступ запрещён. Эта команда доступна только владельцу бота.")
    await message.delete()
    

@router.callback_query(F.data == "admin_stats", is_owner)
async def admin_stats_handler(call: CallbackQuery):
    """Обработчик кнопки «Статистика»."""
    await call.answer()
    
    # Асинхронные запросы к БД (не блокируем event loop)
    total_users = await asyncio.to_thread(db.get_total_users_count)
    today_qs = await asyncio.to_thread(db.get_questions_count_today)
    yesterday_qs = await asyncio.to_thread(db.get_questions_count_yesterday)
    
    # ✅ Статистика токенов (за всё время)
    token_stats = await asyncio.to_thread(db.get_token_stats, user_id=None)  # None = все пользователи

    text = (
        f"📊 <b>Общая статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"📅 Вопросов сгенерировано сегодня: <b>{today_qs}</b>\n"
        f"📅 Вопросов сгенерировано вчера: <b>{yesterday_qs}</b>\n\n"
        f"🪙 <b>Расход токенов (всё время):</b>\n"
        f"• 📝 Генерация вопросов: <b>{token_stats['generation']:,}</b>\n"
        f"• ✅ Оценка ответов: <b>{token_stats['evaluation']:,}</b>\n"
        f"• 📊 <b>Всего:</b> {token_stats['total']:,} токенов"
    )
    # Обновляем сообщение, сохраняя клавиатуру
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_close", is_owner)
async def admin_back(call: CallbackQuery):
    await call.answer()
    await call.message.delete()


@router.callback_query(F.data == "admin_tokens_day", is_owner)
async def admin_tokens_day(call: CallbackQuery):
    """Токены за последние 24 часа."""
    await call.answer()
    stats = await asyncio.to_thread(db.get_token_stats, user_id=None, days=1)
    text = (
        f"🪙 <b>Токены за сутки</b>\n\n"
        f"📝 Генерация: <b>{stats['generation']:,}</b>\n"
        f"✅ Оценка: <b>{stats['evaluation']:,}</b>\n"
        f"📊 <b>Всего:</b> {stats['total']:,} токенов"
    )
    await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_users", is_owner)
@router.callback_query(F.data.startswith("admin_users:page:"), is_owner)
async def admin_users_handler(call: CallbackQuery):
    """Список пользователей с пагинацией."""
    await call.answer()
    
    # Определяем текущую страницу
    page = 0
    if call.data.startswith("admin_users:page:"):
        try:
            page = int(call.data.split(":")[2])
        except (IndexError, ValueError):
            page = 0

    total_users = await asyncio.to_thread(db.get_total_users_count)
    total_pages = math.ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1
    offset = page * USERS_PER_PAGE

    users = await asyncio.to_thread(db.get_users_paginated, limit=USERS_PER_PAGE, offset=offset)

    kb = InlineKeyboardBuilder()
    for (u_id,) in users:
        kb.row(InlineKeyboardButton(text=f"👤 {u_id}", callback_data=f"admin_user_info:{u_id}"))

    kb.attach(build_pagination_keyboard(page, total_pages, "admin_users"))
    kb.row(InlineKeyboardButton(text="🔙 В меню админа", callback_data="admin_back_to_menu"))

    text = f"👥 <b>Пользователи (стр. {page + 1}/{total_pages})</b>\n\nВсего в базе: <b>{total_users}</b>"
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "admin_back_to_menu", is_owner)
async def admin_back_to_menu(call: CallbackQuery):
    """Возврат в главное меню админки."""
    await call.answer()
    await call.message.edit_text(text=ADMIN_WELCOME, reply_markup=admin_keyboard(), parse_mode="HTML")
    
    
@router.callback_query(F.data == "noop", is_owner)
async def noop_handler(call: CallbackQuery):
    """Заглушка для клика по индикатору страницы (чтобы Telegram не ругался)."""
    await call.answer()
    
