# logic/report/report_generator.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем нашу новую асинхронную функцию агрегации аналитики
from database.requests import get_user_analytics_data
from utils.logger import logger

router = Router()

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
    """Кнопка возврата к выбору периодов отчетов."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 К выбору периода", callback_data="report_back_to_menu"))
    kb.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close_callback"))
    return kb.as_markup()

# ===================== ФОРМАТТЕРЫ =====================
def format_stats_text(stats: dict, period: str = "всё время") -> str:
    """Формирует структурированный и красивый текст отчёта."""
    total = stats['total']
    if total == 0:
        return (
            f"📊 <b>Статистика ({period})</b>\n\n"
            f"❌ Пока нет данных для анализа.\n"
            f"Пройдите викторину по файлам вашей базы знаний, чтобы сформировать первый отчёт!"
        )
    
    avg = stats['avg_rating']
    correct_pct = round(stats['correct'] / total * 100) if total else 0
    partial_pct = round(stats['partial'] / total * 100) if total else 0
    wrong_pct = round(stats['wrong'] / total * 100) if total else 0
    
    # Визуализация среднего балла звездочками
    stars = "⭐" * round(avg) + "☆" * (5 - round(avg))
    
    text = (
        f"📊 <b>Статистика ({period})</b>\n\n"
        f"📈 <b>Общие показатели:</b>\n"
        f"• Всего вопросов: <b>{total}</b>\n"
        f"• Средний балл: <b>{avg}/5</b> {stars}\n\n"
        f"🎯 <b>Точность ответов:</b>\n"
        f"• ✅ Правильно: <b>{stats['correct']}</b> ({correct_pct}%)\n"
        f"• 🔶 Частично: <b>{stats['partial']}</b> ({partial_pct}%)\n"
        f"• ❌ Неправильно: <b>{stats['wrong']}</b> ({wrong_pct}%)\n"
    )
    
    # Блок топ-файлов по активности
    if stats['top_files']:
        text += f"\n📚 <b>Активные файлы:</b>\n"
        for fname, cnt in stats['top_files']:
            # Обрезаем слишком длинные названия файлов для визуального баланса
            display_name = fname if len(fname) <= 25 else fname[:22] + "..."
            text += f"• <code>{display_name}</code>: {cnt} вопр.\n"
    
    # Блок текстового мини-графика динамики
    if stats['daily'] and len(stats['daily']) > 1:
        text += f"\n📅 <b>Динамика за неделю:</b>\n"
        for day, cnt, avg_r in stats['daily']:
            # Формируем псевдографику. Ограничиваем длину полосы максимум 8 символами
            bar = "█" * min(cnt, 8)
            current_avg = avg_r or 0.0
            text += f"• {day}: {bar} ({cnt} шт, {current_avg:.1f}⭐)\n"
    
    return text

# ===================== HANDLERS =====================
@router.message(F.text == "📊 Анализ")
async def report_menu(message: Message):
    """Точка входа в раздел «Анализ»."""
    await message.answer(
        "📊 <b>Анализ и статистика</b>\n\n"
        "Выберите интересующий период для расчёта и вывода аналитического отчёта нейросети:",
        reply_markup=report_keyboard(),
        parse_mode="HTML"
    )
    try:
        await message.delete()
    except Exception:
        pass

@router.callback_query(F.data == "report_day")
async def report_day(call: CallbackQuery):
    """Показывает статистику за последние 24 часа."""
    await call.answer()
    stats = await get_user_analytics_data(call.from_user.id, days=1)
    text = format_stats_text(stats, "за сутки")
    await call.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "report_week")
async def report_week(call: CallbackQuery):
    """Показывает статистику за последние 7 дней."""
    await call.answer()
    stats = await get_user_analytics_data(call.from_user.id, days=7)
    text = format_stats_text(stats, "за неделю")
    await call.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "report_overall")
async def report_overall(call: CallbackQuery):
    """Показывает статистику за всё время."""
    await call.answer()
    stats = await get_user_analytics_data(call.from_user.id)
    text = format_stats_text(stats, "всё время")
    await call.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "report_back_to_menu")
async def report_back_to_menu(call: CallbackQuery):
    """Позволяет вернуться назад к выбору периодов без генерации новых сообщений."""
    await call.answer()
    await call.message.edit_text(
        "📊 <b>Анализ и статистика</b>\n\n"
        "Выберите интересующий период для расчёта и вывода аналитического отчёта нейросети:",
        reply_markup=report_keyboard(),
        parse_mode="HTML"
    )

# ===================== ЭКСПОРТ (заготовка) =====================
@router.callback_query(F.data == "report_export")
async def report_export(call: CallbackQuery):
    """Заготовка для экспорта отчёта."""
    await call.answer("🚧 Функция экспорта в PDF/CSV находится в разработке!", show_alert=True)
