# utils/reminders/scheduler.py
import zoneinfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from logic.reminders.reminder_tasks import send_study_reminder
from aiogram import Bot
from utils.logger import logger

def setup_reminder_scheduler(bot: Bot) -> AsyncIOScheduler:
    # Укажите ваш часовой пояс (Europe/Moscow, Europe/Minsk, Europe/Kyiv и т.д.)
    tz = zoneinfo.ZoneInfo("Europe/Moscow")
    
    scheduler = AsyncIOScheduler(timezone=tz)
    
    # 🌅 Утреннее напоминание (каждый день в 9:00)
    scheduler.add_job(
        send_study_reminder,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="morning_study_reminder",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("⏰ Reminder scheduler started successfully.")
    return scheduler

