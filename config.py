# config.py

from dataclasses import dataclass
from environs import Env

@dataclass
class TgBot:
    token: str
    owner_id: int

@dataclass
class AIConfig:
    api_key: str
    base_url: str = "https://vedai.by/api/v1"
    model: str = "gpt-5-nano"
    temperature: float = 0.7
    max_tokens: int = 500

@dataclass
class Config:
    bot: TgBot
    ai: AIConfig

# Инициализация окружения
env = Env()
env.read_env()

# Сборка конфига
config = Config(
    bot=TgBot(
        token=env.str('BOT_TOKEN'),
        owner_id=env.int('OWNER_ID')
    ),
    ai=AIConfig(
        api_key=env.str('AI_API_KEY'),
        base_url=env.str('AI_BASE_URL', 'https://vedai.by/api/v1'),
        model=env.str('AI_MODEL', 'gpt-5-nano'),
        temperature=env.float('AI_TEMPERATURE', 0.7),
        max_tokens=env.int('AI_MAX_TOKENS', 500)
    )
)

