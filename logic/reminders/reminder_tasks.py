# logic/reminders/reminder_tasks.py
import asyncio
from aiogram import Bot
from database.requests import get_users_for_reminders
from utils.logger import logger

async def send_study_reminder(bot: Bot):
    """Отправляет утреннее напоминание всем пользователям с reminders=1"""
    # ✅ Нативно получаем список ID пользователей через ORM
    users = await get_users_for_reminders()
    
    if not users:
        logger.info("🔔 No users with reminders enabled.")
        return

    logger.info(f"🔔 Sending reminders to {len(users)} users.")
    
    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "⏰ <b>Напоминание!</b>\n\n"
                    "Самое время заняться изучением материалов! 📚✨\n\n"
                    "Регулярные занятия помогут закрепить знания. "
                    "Откройте раздел <b>«Викторина»</b> или загрузите новый файл!"
                ),
                parse_mode="HTML"
            )
            # Небольшая задержка между отправками во избежание Flood Control со стороны API Telegram
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"❌ Failed to send reminder to {user_id}: {e}")
