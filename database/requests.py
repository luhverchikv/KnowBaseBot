# database/requests.py
from database.models import async_session, User, Category, Item
from sqlalchemy import select, update, delete


# ==== работа с пользователем ===
async def set_user(user_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))
        if not user:
            session.add(User(user_id=user_id))
            await session.commit()
            return True
        return False
        

async def set_user_difficulty(user_id: int, difficulty: str) -> None:
    """
    Обновляет уровень сложности (difficulty) для пользователя.
    Принимает значения: 'easy', 'medium', 'hard'.
    """
    # Дополнительная валидация на уровне Python (в соответствии с CheckConstraint в модели)
    if difficulty not in ('easy', 'medium', 'hard'):
        difficulty = 'medium'  # Значение по умолчанию, если передано что-то некорректное

    async with async_session() as session:
        # Используем конструкцию update()
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(difficulty=difficulty)
        )
        # Обязательно сохраняем изменения
        await session.commit()


# ==== управление файлами ========
async def get_user_max_file_size(user_id: int) -> float:
    """
    Возвращает максимальный разрешенный размер файла (в МБ) для конкретного пользователя.
    """
    async with async_session() as session:
        # Получаем значение конкретного столбца max_file_size_mb
        result = await session.execute(
            select(User.max_file_size_mb).where(User.user_id == user_id)
        )
        max_size = result.scalar_one_or_none()
        
        # Если пользователь найден, возвращаем его лимит, иначе дефолтное значение
        return max_size if max_size is not None else 0.25


