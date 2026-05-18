# logic/reminders/reminder_tasks.py
import asyncio
from aiogram import Bot
from logic.manage.db import Database
from utils.logger import logger

db = Database()

async def send_study_reminder(bot: Bot):
    """Отправляет утреннее напоминание всем пользователям с reminders=1"""
    # Асинхронно получаем список пользователей
    users = await asyncio.to_thread(db.get_users_by_reminders, 1)
    
    if not users:
        logger.info(" No users with reminders enabled.")
        return

    logger.info(f"🔔 Sending reminders to {len(users)} users.")
    
    for (user_id,) in users:
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
            # Небольшая задержка, чтобы не спамить API
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"❌ Failed to send reminder to {user_id}: {e}")

