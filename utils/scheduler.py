# utils/scheduler.py
import zoneinfo
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from logic.reminders.reminder_tasks import send_study_reminder
from logic.reminders.daily_report import send_daily_analytics
from aiogram import Bot
from config import config
from utils.logger import logger

def setup_reminder_scheduler(bot: Bot) -> AsyncIOScheduler:
    tz = zoneinfo.ZoneInfo("Europe/Minsk")  # Ваш часовой пояс
    scheduler = AsyncIOScheduler(timezone=tz)
    
    # 1. 🌅 Утреннее напоминание пользователям (9:00)
    scheduler.add_job(
        send_study_reminder,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="morning_study_reminder",
        replace_existing=True
    )
    
    # 2. 🧪 Тестовая отправка аналитики через 1 минуту после старта
    # ✅ ВАЖНО: используем datetime.now(tz), чтобы время было "aware" и совпадало с планировщиком
    next_run = datetime.now(tz) + timedelta(minutes=1)
    logger.info(f"⏳ Scheduling test analytics job for: {next_run}")
    
    scheduler.add_job(
        send_daily_analytics,
        DateTrigger(run_date=next_run),
        args=[bot, config.bot.owner_id],
        id="daily_analytics_test",
        replace_existing=True
    )

    # 3. 📊 Ежедневная аналитика админу (7:00)
    # Раскомментируйте для продакшена, когда тест пройдет успешно
    scheduler.add_job(
        send_daily_analytics,
        CronTrigger(hour=7, minute=0),
        args=[bot, config.bot.owner_id],
        id="daily_analytics_report",
        replace_existing=True
        )
    
    scheduler.start()
    logger.info("⏰ Reminder scheduler started successfully.")
    return scheduler

