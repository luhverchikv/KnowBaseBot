# utils/logger.py

import json
import sys
from datetime import datetime
from loguru import logger

def setup_logging():
    """Настройка логирования для всего приложения"""
    
    # Удаляем все стандартные обработчики
    logger.remove()
    
    # Настройка JSON-форматирования для логов
    def json_formatter(record):
        record["extra"]["serialized"] = json.dumps({
            "timestamp": datetime.utcfromtimestamp(record["time"].timestamp()).isoformat() + "Z",
            "level": record["level"].name,
            "message": record["message"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
            **record["extra"]
        }, default=str)
        return "{extra[serialized]}\n"
    
    # Лог ошибок в файл (JSON формат)
    logger.add(
        'logs/errors.log',
        format=json_formatter,
        level="ERROR",
        rotation="1 month",
        compression="zip",
        filter=lambda record: record["level"].name == "ERROR"
    )
    
    # Лог информации в файл (JSON формат)
    logger.add(
        'logs/info.log',
        format=json_formatter,
        level="INFO",
        rotation="1 month",
        compression="zip",
        filter=lambda record: record["level"].name == "INFO"
    )
    
    # Вывод в консоль для разработки (красивый формат)
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # Дополнительный debug лог для разработки
    logger.add(
        'logs/debug.log',
        format=json_formatter,
        level="DEBUG",
        rotation="1 week",
        compression="zip",
        filter=lambda record: record["level"].name == "DEBUG"
    )
    
    logger.info("Logging setup completed")

# Утилиты для структурированного логирования
def get_user_context(user) -> dict:
    """Создает контекст пользователя для логирования"""
    if not user:
        return {}
    
    return {
        "user_id": user.id,
    }

def log_command(message, command: str):
    """Логирует выполнение команды"""
    context = get_user_context(message.from_user)
    context.update({
        "command": command,
        "message_id": message.message_id,
        "event_type": "command_execution"
    })
    logger.bind(**context).info("command_received")

def log_callback(call, handler_name: str):
    """Логирует callback запрос"""
    context = get_user_context(call.from_user)
    context.update({
        "callback_data": call.data,
        "message_id": call.message.message_id,
        "event_type": "callback_query",
        "handler": handler_name
    })
    logger.bind(**context).info("callback_received")

def log_message_sent(user, message_type: str, **additional_context):
    """Логирует отправку сообщения"""
    context = get_user_context(user)
    context.update({
        "event_type": "message_sent",
        "message_type": message_type,
        **additional_context
    })
    logger.bind(**context).info("message_sent")

def log_error(error_msg: str, user=None, **context):
    """Логирует ошибку с контекстом"""
    user_context = get_user_context(user) if user else {}
    logger.bind(**user_context, **context, event_type="error").error(error_msg)


def log_button_click(message, button_text: str, handler_name: str):
    """Логирует нажатие текстовой кнопки"""
    context = get_user_context(message.from_user)
    context.update({
        "button_text": button_text,
        "message_id": message.message_id,
        "event_type": "button_click",
        "handler": handler_name
    })
    logger.bind(**context).info("button_clicked")


# Экспортируем настроенный логгер
__all__ = ['logger', 'setup_logging', 'log_command', 'log_callback', 'log_message_sent', 'log_error', 'get_user_context', 'log_button_click']