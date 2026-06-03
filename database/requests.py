# database/requests.py
from database.models import async_session, User, QuizQuestion, Feedback, File
from sqlalchemy import select, update, delete, func, update
import random
from datetime import datetime, time
from logic.ai_connector import TokenUsage



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


# database/requests.py

# --- Функции получения лимитов и настроек пользователя ---

async def get_user_max_questions_per_day(user_id: int) -> int:
    """Получает лимит количества вопросов в день для пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(User.max_questions_per_day).where(User.user_id == user_id)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else 5




async def get_daily_questions_count(user_id: int) -> int:
    """Считает количество сгенерированных вопросов для пользователя за текущие сутки."""
    async with async_session() as session:
        # Границы текущих суток
        start_of_day = datetime.combine(datetime.now().date(), time.min)
        
        result = await session.execute(
            select(func.count(QuizQuestion.id)).where(
                QuizQuestion.user_id == user_id,
                QuizQuestion.generated_at >= start_of_day
            )
        )
        return result.scalar_or_none() or 0

# --- Работа с вопросами квиза через ORM ---

async def add_quiz_question(user_id: int, source_file: str, question: str, correct_answer: str, gen_tokens: TokenUsage = None) -> int:
    """Создает новую запись вопроса в БД и сохраняет токены генерации. Возвращает ID записи."""
    async with async_session() as session:
        new_q = QuizQuestion(
            user_id=user_id,
            source_file=source_file,
            question=question,
            correct_answer=correct_answer,
            gen_prompt_tokens=gen_tokens.prompt_tokens if gen_tokens else 0,
            gen_completion_tokens=gen_tokens.completion_tokens if gen_tokens else 0,
            gen_total_tokens=gen_tokens.total_tokens if gen_tokens else 0
        )
        session.add(new_q)
        await session.commit()
        return new_q.id

async def update_quiz_result(q_id: int, user_answer: str, correctness: str, feedback: str, rating: int, eval_tokens: TokenUsage = None) -> None:
    """Обновляет запись вопроса: сохраняет ответ пользователя, оценку, отзыв ИИ и токены оценки."""
    async with async_session() as session:
        stmt = (
            update(QuizQuestion)
            .where(QuizQuestion.id == q_id)
            .values(
                user_answer=user_answer,
                correctness=correctness,
                feedback=feedback,
                rating=rating,
                eval_prompt_tokens=eval_tokens.prompt_tokens if eval_tokens else 0,
                eval_completion_tokens=eval_tokens.completion_tokens if eval_tokens else 0,
                eval_total_tokens=eval_tokens.total_tokens if eval_tokens else 0
            )
        )
        await session.execute(stmt)
        await session.commit()

# ==== работа с отзывами ====
async def save_feedback(user_id: int, feedback_text: str) -> None:
    """
    Асинхронно сохраняет отзыв пользователя в базу данных.
    Поля id, created_at (func.now()) и is_read (server_default=0) заполняются автоматически на стороне СУБД.
    """
    async with async_session() as session:
        new_feedback = Feedback(
            user_id=user_id,
            feedback_text=feedback_text
        )
        session.add(new_feedback)
        await session.commit()


async def get_user_difficulty(user_id: int) -> str:
    """Получает уровень сложности пользователя ('easy', 'medium', 'hard')."""
    async with async_session() as session:
        result = await session.execute(
            select(User.difficulty).where(User.user_id == user_id)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else "medium"

async def set_user_difficulty(user_id: int, difficulty: str) -> None:
    """Обновляет уровень сложности пользователя в БД."""
    async with async_session() as session:
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(difficulty=difficulty)
        )
        await session.execute(stmt)
        await session.commit()

async def get_user_reminders(user_id: int) -> int:
    """Получает статус напоминаний пользователя (0 или 1)."""
    async with async_session() as session:
        result = await session.execute(
            select(User.reminders).where(User.user_id == user_id)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else 0

async def set_user_reminders(user_id: int, reminders: int) -> None:
    """Обновляет статус напоминаний пользователя в БД."""
    async with async_session() as session:
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(reminders=reminders)
        )
        await session.execute(stmt)
        await session.commit()
