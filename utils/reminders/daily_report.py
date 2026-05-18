# utils/reminders/daily_report.py
import asyncio
from aiogram import Bot
from logic.manage.db import Database
from utils.logger import logger

db = Database()

async def send_daily_analytics(bot: Bot, owner_id: int):
    """Отправляет утреннюю аналитику владельцу бота."""
    try:
        summary = await asyncio.to_thread(db.get_daily_summary)
        
        # Форматируем числа с разделителями тысяч
        def fmt(n: int) -> str:
            return f"{n:,}".replace(",", " ")
        
        text = (
            f"📊 <b>Утренняя аналитика</b> • {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"👥 <b>Пользователи:</b>\n"
            f"• Всего: <b>{fmt(summary['total_users'])}</b>\n\n"
            f"📅 <b>Вчера:</b>\n"
            f"• Вопросов: <b>{fmt(summary['yesterday']['questions'])}</b>\n"
            f"• Токенов: <b>{fmt(summary['yesterday']['total_tokens'])}</b>\n"
            f"  ├─ Генерация: {fmt(summary['yesterday']['gen_tokens'])}\n"
            f"  └─ Оценка: {fmt(summary['yesterday']['eval_tokens'])}\n\n"
            f"🌅 <b>Сегодня (на 07:00):</b>\n"
            f"• Вопросов: <b>{fmt(summary['today']['questions'])}</b>\n"
            f"• Токенов: <b>{fmt(summary['today']['total_tokens'])}</b>\n"
            f"  ├─ Генерация: {fmt(summary['today']['gen_tokens'])}\n"
            f"  └─ Оценка: {fmt(summary['today']['eval_tokens'])}"
        )
        
        await bot.send_message(
            chat_id=owner_id,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"✅ Daily analytics sent to owner {owner_id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to send daily analytics: {e}")

