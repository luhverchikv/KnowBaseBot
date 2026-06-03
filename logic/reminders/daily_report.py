# logic/reminders/daily_report.py
import datetime
from aiogram import Bot
from database.requests import get_daily_summary_data, get_latest_unread_feedback
from utils.logger import logger

async def send_daily_analytics(bot: Bot, owner_id: int):
    """Отправляет утреннюю аналитику владельцу бота."""
    try:
        # ✅ Получаем агрегированные данные из БД через ORM
        summary = await get_daily_summary_data()
        
        # Функция форматирования чисел с разделителями тысяч
        def fmt(n: int) -> str:
            return f"{n:,}".replace(",", " ")
        
        # ✅ Получаем список непрочитанных отзывов из новой ORM функции
        unread_feedback = await get_latest_unread_feedback(limit=5)
        
        # Формируем красивый блок отзывов
        feedback_block = ""
        if unread_feedback:
            feedback_block = f"\n\n💬 <b>Новые отзывы ({len(unread_feedback)}):</b>\n"
            for fb in unread_feedback:
                preview = fb['text'][:100] + ("..." if len(fb['text']) > 100 else "")
                feedback_block += f"• 👤 <code>{fb['tg_id']}</code> • <i>{fb['created_at']}</i>\n  <i>{preview}</i>\n"
            if len(unread_feedback) == 5:
                feedback_block += f"\n<i>Есть ещё непрочитанные отзывы. Проверьте в админ-панели.</i>"
        else:
            feedback_block = "\n\n✅ <b>Новых непрочитанных отзывов нет.</b>"
        
        # Строим текст отчета
        text = (
            f"📊 <b>Утренняя аналитика</b> • {datetime.datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"👥 <b>Пользователи:</b>\n"
            f"• Всего: <b>{fmt(summary['total_users'])}</b>\n\n"
            f"📅 <b>Вчера:</b>\n"
            f"• Вопросов: <b>{fmt(summary['yesterday']['questions'])}</b>\n"
            f"• Токенов: <b>{fmt(summary['yesterday']['total_tokens'])}</b>\n"
            f"  ├─ Генерация: {fmt(summary['yesterday']['gen_tokens'])}\n"
            f"  └─ Оценка: {fmt(summary['yesterday']['eval_tokens'])}\n\n"
            f"🌅 <b>Сегодня (на момент отчёта):</b>\n"
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
        logger.exception(f"❌ Failed to send daily analytics: {e}")
