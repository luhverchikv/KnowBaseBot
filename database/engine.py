# database/engine.py
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Путь к БД (создаётся в папке database/)
DB_PATH = Path(__file__).parent.parent / "database" / "knowbase.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH.resolve()}"

# Асинхронный движок
engine = create_async_engine(
    DB_URL, 
    echo=False,  # Поставьте True для отладки SQL-запросов
    pool_pre_ping=True
)

# Фабрика сессий. expire_on_commit=False критичен для aiogram,
# чтобы объекты не теряли состояние после commit
async_session = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Базовый класс для моделей
Base = DeclarativeBase()

async def init_db():
    """Создаёт таблицы, если их нет"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных и таблицы инициализированы")

