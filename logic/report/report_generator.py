# logic/report/report_generator.py
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from logic.manage.db import Database
from utils.logger import logger

router = Router()
db = Database()

# ===================== КЛАВИАТУРЫ =====================
def report_keyboard():
    """Собирает inline-клавиатуру для раздела «Анализ»."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 За сутки", callback_data="report_day"),
        InlineKeyboardButton(text="📅 За неделю", callback_data="report_week")
    )
    kb.row(InlineKeyboardButton(text="📈 За всё время", callback_data="report_overall"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_callback"))
    return kb.as_markup()

def back_to_menu_keyboard():
    """Кнопка возврата в главное меню."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="report_back"))
    return kb.as_markup()

# ===================== DB WRAPPERS (async-safe) =====================
async def get_user_stats(user_id: int, days: int = None) -> dict:
    """
    Собирает статистику пользователя.
    Если days указан — фильтрует по периоду.
    """
    def _query():
        where = f"AND DATE(generated_at) >= DATE('now', '-{days} days')" if days else ""
        
        # Общая статистика
        db.cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                AVG(rating) as avg_rating,
                SUM(CASE WHEN correctness='правильно' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN correctness='частично' THEN 1 ELSE 0 END) as partial,
                SUM(CASE WHEN correctness='неправильно' THEN 1 ELSE 0 END) as wrong
            FROM quiz_questions 
            WHERE user_id = ? {where}
        """, (user_id,))
        row = db.cursor.fetchone()
        
        # Топ файлов по количеству вопросов
        db.cursor.execute(f"""
            SELECT source_file, COUNT(*) as cnt 
            FROM quiz_questions 
            WHERE user_id = ? {where}
            GROUP BY source_file 
            ORDER BY cnt DESC 
            LIMIT 3
        """, (user_id,))
        top_files = db.cursor.fetchall()
        
        # Динамика по дням (последние 7 дней или меньше, если период короче)
        limit_days = min(days, 7) if days else 7
        db.cursor.execute(f"""
            SELECT DATE(generated_at) as day, COUNT(*) as cnt, AVG(rating) as avg_r
            FROM quiz_questions 
            WHERE user_id = ? AND DATE(generated_at) >= DATE('now', '-{limit_days} days')
            GROUP BY day 
            ORDER BY day
        """, (user_id,))
        daily = db.cursor.fetchall()
        
        return {
            'total': row[0] or 0,
            'avg_rating': round(row[1], 2) if row[1] else 0.0,
            'correct': row[2] or 0,
            'partial': row[3] or 0,
            'wrong': row[4] or 0,
            'top_files': top_files,
            'daily': daily
        }
    
    return await asyncio.to_thread(_query)

# ===================== ФОРМАТТЕРЫ =====================
def format_stats_text(stats: dict, period: str = "всё время") -> str:
    """Формирует красивый текст отчёта."""
    total = stats['total']
    if total == 0:
        return f"📊 <b>Статистика ({period})</b>\n\n❌ Пока нет данных. Пройдите викторину, чтобы увидеть отчёт!"
    
    avg = stats['avg_rating']
    correct_pct = round(stats['correct'] / total * 100) if total else 0
    partial_pct = round(stats['partial'] / total * 100) if total else 0
    wrong_pct = round(stats['wrong'] / total * 100) if total else 0
    
    # Визуализация рейтинга
    stars = "⭐" * round(avg) + "☆" * (5 - round(avg))
    
    text = (
        f"📊 <b>Статистика ({period})</b>\n\n"
        f"📈 <b>Общие показатели:</b>\n"
        f"• Всего вопросов: <b>{total}</b>\n"
        f"• Средний балл: <b>{avg}/5</b> {stars}\n\n"
        f"🎯 <b>Точность:</b>\n"
        f"• ✅ Правильно: <b>{stats['correct']}</b> ({correct_pct}%)\n"
        f"• 🔶 Частично: <b>{stats['partial']}</b> ({partial_pct}%)\n"
        f"• ❌ Неправильно: <b>{stats['wrong']}</b> ({wrong_pct}%)\n"
    )
    
    # Топ файлов
    if stats['top_files']:
        text += f"\n📚 <b>Активные файлы:</b>\n"
        for fname, cnt in stats['top_files'][:3]:
            text += f"• <code>{fname}</code>: {cnt} вопросов\n"
    
    # Мини-график динамики (текстовый)
    if stats['daily'] and len(stats['daily']) > 1:
        text += f"\n📅 <b>Динамика:</b>\n"
        for day, cnt, avg_r in stats['daily']:
            bar = "█" * min(cnt, 10)
            text += f"• {day}: {bar} ({cnt}, ср. {avg_r or 0:.1f}⭐)\n"
    
    return text

# ===================== HANDLERS =====================
@router.message(F.text == "📊 Анализ")
async def report_menu(message: Message):
    """Точка входа в раздел «Анализ»."""
    await message.answer(
        "📊 <b>Анализ и статистика</b>\n\n"
        "Выберите период для просмотра отчёта:",
        reply_markup=report_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "report_day")
async def report_day(call: CallbackQuery):
    """Показывает статистику за последние 24 часа."""
    await call.answer()
    stats = await get_user_stats(call.from_user.id, days=1)
    text = format_stats_text(stats, "за сутки")
    await call.message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "report_week")
async def report_week(call: CallbackQuery):
    """Показывает статистику за последнюю неделю."""
    await call.answer()
    stats = await get_user_stats(call.from_user.id, days=7)
    text = format_stats_text(stats, "за неделю")
    await call.message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "report_overall")
async def report_overall(call: CallbackQuery):
    """Показывает статистику за всё время."""
    await call.answer()
    stats = await get_user_stats(call.from_user.id)
    text = format_stats_text(stats, "всё время")
    await call.message.answer(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "report_back")
async def report_back(call: CallbackQuery):
    """Возврат в главное меню."""
    await call.answer()
    from menu.start_menu import start_text, start_keyboard
    await call.message.edit_text(
        text=start_text,
        reply_markup=start_keyboard(),
        parse_mode="HTML"
    )

# ===================== ЭКСПОРТ (заготовка) =====================
@router.callback_query(F.data == "report_export")
async def report_export(call: CallbackQuery):
    """Заготовка для экспорта отчёта (будет реализовано позже)."""
    await call.answer("🚧 Функция экспорта в разработке!", show_alert=True)

