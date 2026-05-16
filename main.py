# main.py

import asyncio
from aiogram import Bot, Dispatcher
from config import config
from utils.logger import setup_logging, logger
from logic.ai_connector import ai_client
from menu.start_menu import router as menu_router
from logic.manage.knowledge_base import router as kb_router
from logic.quiz import router as quiz_router
from logic.report.report_generator import router as report_router 


async def main():
    
    setup_logging()
    logger.info("Starting bot application")

    bot = Bot(config.bot.token)
    dp = Dispatcher()

    logger.bind(bot_id=bot.id).info("Bot instance created")

    dp.include_router(menu_router)
    dp.include_router(kb_router)
    dp.include_router(quiz_router)
    dp.include_router(report_router) 
    
    try:
        logger.info("Starting bot polling")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error("Bot polling failed: {}", str(e))
        raise
    finally:
        await ai_client.close()
        logger.info("Bot shutting down")


if __name__ == "__main__":
    asyncio.run(main())