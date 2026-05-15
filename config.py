# config.py

from dataclasses import dataclass
from environs import Env


@dataclass
class TgBot:
    token: str
    owner_id: int


@dataclass
class Config:
    bot: TgBot


# Инициализация Env
env = Env()
env.read_env()  # Читаем из .env файла в корне проекта


# Создаем конфиг
config = Config(
    bot=TgBot(
        token=env('BOT_TOKEN'),
        owner_id=env.int('OWNER_ID')
    ),
)