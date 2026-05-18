# utils/reminders/scheduler.py
import zoneinfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from logic.reminders.reminder_tasks import send_study_reminder
from utils.reminders.daily_report import send_daily_analytics  # ✅ Новый импорт
from aiogram import Bot
from config import config  # ✅ Для доступа к owner_id
from utils.logger import logger

def setup_reminder_scheduler(bot: Bot) -> AsyncIOScheduler:
    tz = zoneinfo.ZoneInfo("Europe/Moscow")  # Укажите ваш часовой пояс
    scheduler = AsyncIOScheduler(timezone=tz)
    
    # 🌅 Утреннее напоминание пользователям (9:00)
    scheduler.add_job(
        send_study_reminder,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="morning_study_reminder",
        replace_existing=True
    )
    
    # 📊 Утренняя аналитика админу (7:00)
    scheduler.add_job(
        send_daily_analytics,
        CronTrigger(hour=7, minute=0),
        args=[bot, config.bot.owner_id],  # ✅ Передаём bot и owner_id
        id="daily_analytics_report",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("⏰ Reminder scheduler started successfully.")
    return scheduler

