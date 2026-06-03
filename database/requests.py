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


async def get_user_max_files(user_id: int) -> int:
    """
    Возвращает максимальное количество файлов, разрешенное пользователю.
    """
    async with async_session() as session:
        result = await session.execute(
            select(User.max_files).where(User.user_id == user_id)
        )
        max_files = result.scalar_one_or_none()
        
        # Если пользователь найден, возвращаем его лимит, иначе дефолтное значение 3
        return max_files if max_files is not None else 3


async def add_file_to_db(user_id: int, filename: str, file_path: str, description: str = "Краткое описание") -> None:
    """
    Добавляет информацию о загруженном файле в таблицу files.
    """
    async with async_session() as session:
        new_file = File(
            user_id=user_id,
            filename=filename,
            file_path=str(file_path),
            description=description  # Теперь записывается сгенерированное ИИ описание
        )
        session.add(new_file)
        await session.commit()
        

async def get_user_files(user_id: int) -> list[File]:
    """
    Возвращает список всех файлов пользователя из базы данных.
    """
    async with async_session() as session:
        result = await session.execute(
            select(File).where(File.user_id == user_id).order_by(File.filename)
        )
        # .scalars().all() превращает результат в обычный список объектов модели File
        return list(result.scalars().all())


async def get_file_by_id(file_id: int) -> File | None:
    """
    Возвращает объект файла по его первичному ключу ID.
    """
    async with async_session() as session:
        result = await session.execute(
            select(File).where(File.id == file_id)
        )
        return result.scalar_one_or_none()


async def delete_file_from_db(file_id: int) -> File | None:
    """
    Удаляет запись о файле из базы данных по его ID.
    Возвращает объект файла ДО удаления, чтобы можно было получить его путь для стирания с диска.
    """
    async with async_session() as session:
        # 1. Сначала находим запись, чтобы вернуть информацию о ней
        result = await session.execute(
            select(File).where(File.id == file_id)
        )
        file_data = result.scalar_one_or_none()
        
        if file_data:
            # 2. Удаляем запись из БД
            await session.delete(file_data)
            await session.commit()
            return file_data
            
        return None
