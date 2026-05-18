# utils/reminders/daily_report.py
import asyncio
from datetime import datetime
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
        
        # ✅ Получаем непрочитанные отзывы (последние 5)
        unread_feedback = await asyncio.to_thread(db.get_feedback_paginated, limit=5, only_unread=True)
        
        # Формируем блок с отзывами
        feedback_block = ""
        if unread_feedback:
            feedback_block = f"\n\n💬 <b>Новые отзывы ({len(unread_feedback)}):</b>\n"
            for fb_id, user_db_id, fb_text, created_at, tg_id in unread_feedback:
                display_id = tg_id if tg_id else f"user_{user_db_id}"
                preview = fb_text[:100] + ("..." if len(fb_text) > 100 else "")
                feedback_block += f"• 👤 <code>{display_id}</code> • <i>{created_at}</i>\n  <i>{preview}</i>\n"
            if len(unread_feedback) == 5:
                feedback_block += f"\n<i>Есть ещё непрочитанные отзывы. Проверьте в админ-панели.</i>"
        else:
            feedback_block = "\n\n✅ <b>Новых отзывов нет.</b>"
        
        text = (
            f"📊 <b>Утренняя аналитика</b> • {datetime.datetime.now().strftime('%d.%m.%Y')}\n\n"
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
            f"{feedback_block}"
        )
        
        await bot.send_message(
            chat_id=owner_id,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"✅ Daily analytics sent to owner {owner_id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to send daily analytics: {e}")

