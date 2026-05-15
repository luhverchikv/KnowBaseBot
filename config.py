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
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 500

@dataclass
class Config:
    bot: TgBot
    ai
