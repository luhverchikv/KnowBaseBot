# database/requests.py
"""
Модуль работы с базой данных.
Содержит функции для управления пользователями, файлами, викторинами и отзывами.
"""

from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, delete, desc, func, select, update

from database.models import (
    AsyncSession,
    File,
    Feedback,
    GenerationCounter,
    QuizQuestion,
    User,
    async_session,
)
from logic.ai_connector import TokenUsage
from utils.logger import logger


# =============================================================================
# КОНСТАНТЫ И ТИПЫ
# =============================================================================

# Допустимые значения сложности
VALID_DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")

# Дефолтные значения для пользовательских лимитов
DEFAULT_MAX_FILE_SIZE_MB: float = 0.25
DEFAULT_MAX_FILES: int = 3
DEFAULT_MAX_QUESTIONS_PER_DAY: int = 5
DEFAULT_DIFFICULTY: str = "medium"

# Лимиты генераций пулов
FREE_GENERATION_LIMIT: int = 2
VIP_GENERATION_LIMIT: int = 10


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

async def _get_user_field(user_id: int, field_name: str, default: Any) -> Any:
    """
    Универсальная функция для получения поля пользователя.

    Args:
        user_id: Telegram ID пользователя
        field_name: Имя поля модели User
        default: Значение по умолчанию

    Returns:
        Значение поля или default
    """
    async with async_session() as session:
        result = await session.execute(
            select(getattr(User, field_name)).where(User.user_id == user_id)
        )
        value = result.scalar_one_or_none()
        return value if value is not None else default


async def _update_user_field(user_id: int, field_name: str, value: Any) -> None:
    """
    Универсальная функция для обновления поля пользователя.

    Args:
        user_id: Telegram ID пользователя
        field_name: Имя поля модели User
        value: Новое значение
    """
    async with async_session() as session:
        await session.execute(
            update(User).where(User.user_id == user_id).values(**{field_name: value})
        )
        await session.commit()


def _format_datetime(dt: Optional[datetime]) -> str:
    """Форматирует datetime в строку 'DD.MM.YYYY HH:MM'."""
    return dt.strftime("%d.%m.%Y %H:%M") if dt else ""


def _format_date_only(dt: Optional[datetime]) -> str:
    """Форматирует datetime в строку 'DD.MM.YYYY'."""
    return dt.strftime("%d.%m") if dt else ""


# =============================================================================
# РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
# =============================================================================

async def set_user(user_id: int) -> bool:
    """
    Создаёт нового пользователя, если его ещё нет в БД.

    Returns:
        True если пользователь был создан, False если уже существовал
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))
        if not user:
            session.add(User(user_id=user_id))
            await session.commit()
            return True
        return False


async def get_user_difficulty(user_id: int) -> str:
    """Возвращает уровень сложности пользователя."""
    return await _get_user_field(user_id, "difficulty", DEFAULT_DIFFICULTY)


async def set_user_difficulty(user_id: int, difficulty: str) -> None:
    """
    Обновляет уровень сложности для пользователя.

    Args:
        user_id: Telegram ID пользователя
        difficulty: Уровень сложности ('easy', 'medium', 'hard')
    """
    # Валидация на уровне Python
    if difficulty not in VALID_DIFFICULTIES:
        difficulty = DEFAULT_DIFFICULTY

    await _update_user_field(user_id, "difficulty", difficulty)


async def get_user_reminders(user_id: int) -> int:
    """Возвращает статус напоминаний пользователя (0 или 1)."""
    return await _get_user_field(user_id, "reminders", 0)


async def set_user_reminders(user_id: int, reminders: int) -> None:
    """Обновляет статус напоминаний пользователя."""
    await _update_user_field(user_id, "reminders", reminders)


async def get_user_subscription_status(user_id: int) -> Dict[str, Any]:
    """
    Возвращает статус подписки пользователя.

    Returns:
        dict с ключами 'status' ('free' или 'premium') и 'until' (datetime или None)
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))

        if not user:
            return {"status": "free", "until": None}

        # Проверяем, не истекла ли подписка
        if user.subscription_status == "premium" and user.subscription_until:
            if datetime.now() > user.subscription_until:
                user.subscription_status = "free"
                user.subscription_until = None
                await session.commit()
                return {"status": "free", "until": None}

        return {
            "status": user.subscription_status,
            "until": user.subscription_until,
        }


async def upgrade_to_premium(user_id: int, days: int = 30) -> None:
    """Активирует премиум-подписку на указанное количество дней."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))

        if user:
            user.subscription_status = "premium"
            user.subscription_until = datetime.now() + timedelta(days=days)
            await session.commit()


# =============================================================================
# ПОЛЬЗОВАТЕЛЬСКИЕ ЛИМИТЫ И НАСТРОЙКИ
# =============================================================================

async def get_user_max_file_size(user_id: int) -> float:
    """Возвращает максимальный размер файла (МБ) для пользователя."""
    return await _get_user_field(user_id, "max_file_size_mb", DEFAULT_MAX_FILE_SIZE_MB)


async def get_user_max_files(user_id: int) -> int:
    """Возвращает максимальное количество файлов для пользователя."""
    return await _get_user_field(user_id, "max_files", DEFAULT_MAX_FILES)


async def get_user_max_questions_per_day(user_id: int) -> int:
    """Возвращает лимит вопросов в день для пользователя."""
    return await _get_user_field(user_id, "max_questions_per_day", DEFAULT_MAX_QUESTIONS_PER_DAY)


async def get_user_limits_dict(user_id: int) -> Dict[str, Any]:
    """Возвращает все лимиты пользователя в виде словаря."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))
        if not user:
            return {
                "max_questions_per_day": 0,
                "max_files": 0,
                "max_file_size_mb": 0.0,
            }

        return {
            "max_questions_per_day": getattr(user, "max_questions_per_day", 20),
            "max_files": getattr(user, "max_files", 5),
            "max_file_size_mb": getattr(user, "max_file_size_mb", 10.0),
        }


async def update_user_limit_value(user_id: int, field: str, value: Any) -> bool:
    """Обновляет указанный лимит пользователя."""
    await _update_user_field(user_id, field, value)
    return True


async def get_user_profile_counters(user_id: int) -> Tuple[int, int]:
    """Возвращает (количество_вопросов, количество_файлов) для пользователя."""
    async with async_session() as session:
        q_count = (
            await session.scalar(
                select(func.count(QuizQuestion.id)).where(QuizQuestion.user_id == user_id)
            )
            or 0
        )
        f_count = (
            await session.scalar(select(func.count(File.id)).where(File.user_id == user_id))
            or 0
        )
        return q_count, f_count


# =============================================================================
# УПРАВЛЕНИЕ ФАЙЛАМИ
# =============================================================================

async def add_file_to_db(
    user_id: int, filename: str, file_path: str, description: str = "Краткое описание"
) -> None:
    """Добавляет информацию о загруженном файле в таблицу files."""
    async with async_session() as session:
        session.add(
            File(
                user_id=user_id,
                filename=filename,
                file_path=str(file_path),
                description=description,
            )
        )
        await session.commit()


async def get_user_files(user_id: int) -> List[File]:
    """Возвращает список всех файлов пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(File).where(File.user_id == user_id).order_by(File.filename)
        )
        return list(result.scalars().all())


async def get_file_by_id(file_id: int) -> Optional[File]:
    """Возвращает объект файла по его ID."""
    async with async_session() as session:
        result = await session.execute(select(File).where(File.id == file_id))
        return result.scalar_one_or_none()


async def delete_file_from_db(file_id: int) -> Optional[File]:
    """
    Удаляет запись о файле из БД.
    Возвращает объект файла ДО удаления для получения пути к файлу.
    """
    async with async_session() as session:
        result = await session.execute(select(File).where(File.id == file_id))
        file_data = result.scalar_one_or_none()

        if file_data:
            await session.delete(file_data)
            await session.commit()
            return file_data

        return None


# =============================================================================
# РАБОТА С ВОПРОСАМИ ВИКТОРИНЫ
# =============================================================================

async def get_daily_questions_count(user_id: int) -> int:
    """Возвращает количество вопросов, сгенерированных за текущие сутки."""
    start_of_day = datetime.combine(datetime.now().date(), time.min)

    async with async_session() as session:
        result = await session.execute(
            select(func.count(QuizQuestion.id)).where(
                QuizQuestion.user_id == user_id, QuizQuestion.generated_at >= start_of_day
            )
        )
        return result.scalar() or 0


async def add_quiz_question(
    user_id: int,
    source_file: str,
    question: str,
    correct_answer: str,
    gen_tokens: Optional[TokenUsage] = None,
) -> int:
    """
    Создаёт новую запись вопроса в БД.

    Returns:
        ID созданной записи
    """
    async with async_session() as session:
        new_q = QuizQuestion(
            user_id=user_id,
            source_file=source_file,
            question=question,
            correct_answer=correct_answer,
            gen_prompt_tokens=gen_tokens.prompt_tokens if gen_tokens else 0,
            gen_completion_tokens=gen_tokens.completion_tokens if gen_tokens else 0,
            gen_total_tokens=gen_tokens.total_tokens if gen_tokens else 0,
        )
        session.add(new_q)
        await session.commit()
        return new_q.id


async def update_quiz_result(
    q_id: int,
    user_answer: str,
    correctness: str,
    feedback: str,
    rating: int,
    eval_tokens: Optional[TokenUsage] = None,
) -> None:
    """Обновляет запись вопроса: ответ пользователя, оценка и отзыв ИИ."""
    async with async_session() as session:
        await session.execute(
            update(QuizQuestion)
            .where(QuizQuestion.id == q_id)
            .values(
                user_answer=user_answer,
                correctness=correctness,
                feedback=feedback,
                rating=rating,
                eval_prompt_tokens=eval_tokens.prompt_tokens if eval_tokens else 0,
                eval_completion_tokens=eval_tokens.completion_tokens if eval_tokens else 0,
                eval_total_tokens=eval_tokens.total_tokens if eval_tokens else 0,
            )
        )
        await session.commit()


async def get_unanswered_quiz_question(user_id: int) -> Optional[QuizQuestion]:
    """
    Ищет самый старый неотвеченный вопрос для пользователя.

    Returns:
        Объект вопроса или None
    """
    async with async_session() as session:
        result = await session.execute(
            select(QuizQuestion)
            .where(
                QuizQuestion.user_id == user_id,
                (QuizQuestion.user_answer == None) | (QuizQuestion.user_answer == ""),
            )
            .order_by(QuizQuestion.generated_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def add_quiz_questions_batch(
    user_id: int, source_file: str, questions_data: List[Dict], total_gen_tokens: int
) -> int:
    """
    Массовое добавление сгенерированных вопросов в БД.

    Returns:
        Количество успешно добавленных вопросов
    """
    count = len(questions_data)
    if count == 0:
        return 0

    tokens_per_question = total_gen_tokens // count

    async with async_session() as session:
        new_questions = [
            QuizQuestion(
                user_id=user_id,
                source_file=source_file,
                question=q_data["question"],
                correct_answer=q_data["correct_answer"],
                user_answer=None,
                correctness=None,
                feedback=None,
                rating=None,
                gen_total_tokens=tokens_per_question,
            )
            for q_data in questions_data
        ]

        session.add_all(new_questions)
        await session.commit()

    logger.info(f"✅ Успешно добавлено {len(new_questions)} вопросов в БД для пользователя {user_id}")
    return len(new_questions)


async def get_unanswered_questions_count(user_id: int) -> int:
    """
    Возвращает количество неотвеченных вопросов для пользователя.
    """
    async with async_session() as session:
        stmt = (
            select(func.count(QuizQuestion.id))
            .where(
                QuizQuestion.user_id == user_id,
                (QuizQuestion.user_answer == None) | (QuizQuestion.user_answer == "")
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one()
        
        
# =============================================================================
# РАБОТА С ОТЗЫВАМИ
# =============================================================================

async def save_feedback(user_id: int, feedback_text: str) -> None:
    """Сохраняет отзыв пользователя в базу данных."""
    async with async_session() as session:
        session.add(Feedback(user_id=user_id, feedback_text=feedback_text))
        await session.commit()


async def get_feedback_paginated(
    limit: int, offset: int
) -> List[Tuple[int, int, str, str, int]]:
    """
    Возвращает пагинированный список отзывов.

    Returns:
        List[(feedback_id, user_id, text, created_str, tg_id)]
    """
    async with async_session() as session:
        result = await session.execute(
            select(Feedback.id, Feedback.user_id, Feedback.feedback_text, Feedback.created_at, User.user_id)
            .join(User, Feedback.user_id == User.user_id, isouter=True)
            .order_by(Feedback.id.desc())
            .limit(limit)
            .offset(offset)
        )

        return [
            (row[0], row[1], row[2], _format_datetime(row[3]), row[4])
            for row in result.all()
        ]


async def get_feedback_by_id(fb_id: int) -> Optional[Tuple[int, str, str, int]]:
    """Возвращает детальную информацию об отзыве."""
    async with async_session() as session:
        fb = await session.scalar(select(Feedback).where(Feedback.id == fb_id))
        if fb:
            return fb.user_id, fb.feedback_text, _format_datetime(fb.created_at), 1 if fb.is_read else 0
        return None


async def mark_feedback_read(fb_id: int) -> None:
    """Помечает отзыв как прочитанный."""
    async with async_session() as session:
        await session.execute(
            update(Feedback).where(Feedback.id == fb_id).values(is_read=1)
        )
        await session.commit()


async def delete_feedback_by_id(fb_id: int) -> bool:
    """Удаляет отзыв из базы данных."""
    async with async_session() as session:
        await session.execute(delete(Feedback).where(Feedback.id == fb_id))
        await session.commit()
        return True


async def get_unread_feedback_count() -> int:
    """Возвращает количество непрочитанных отзывов."""
    async with async_session() as session:
        return await session.scalar(
            select(func.count(Feedback.id)).where(Feedback.is_read == 0)
        ) or 0


async def get_latest_unread_feedback(limit: int = 5) -> List[Dict[str, Any]]:
    """Возвращает список последних непрочитанных отзывов."""
    async with async_session() as session:
        result = await session.execute(
            select(Feedback, User.user_id)
            .join(User, Feedback.user_id == User.user_id, isouter=True)
            .where(Feedback.is_read == 0)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )

        return [
            {
                "text": row[0].feedback_text,
                "created_at": _format_date_only(row[0].created_at),
                "tg_id": row[0].user_id,
            }
            for row in result.all()
        ]


# =============================================================================
# ГЕНЕРАЦИЯ ПУЛОВ (VIP)
# =============================================================================

async def get_daily_pool_generations(user_id: int) -> int:
    """Возвращает количество генераций пулов за сегодня."""
    today = datetime.now().date()

    async with async_session() as session:
        result = await session.execute(
            select(GenerationCounter).where(
                and_(
                    GenerationCounter.user_id == user_id,
                    func.date(GenerationCounter.date) == today,
                )
            )
        )
        counter = result.scalar_one_or_none()
        return counter.pool_generations if counter else 0


async def increment_pool_generation(user_id: int) -> None:
    """Увеличивает счётчик генераций пулов на 1."""
    today = datetime.now().date()

    async with async_session() as session:
        result = await session.execute(
            select(GenerationCounter).where(
                and_(
                    GenerationCounter.user_id == user_id,
                    func.date(GenerationCounter.date) == today,
                )
            )
        )
        counter = result.scalar_one_or_none()

        if counter:
            counter.pool_generations += 1
        else:
            session.add(
                GenerationCounter(user_id=user_id, date=datetime.now(), pool_generations=1)
            )

        await session.commit()


async def get_generation_limit(user_id: int) -> int:
    """Возвращает лимит генераций для пользователя (Free: 2, VIP: 10)."""
    sub_status = await get_user_subscription_status(user_id)
    return VIP_GENERATION_LIMIT if sub_status["status"] == "premium" else FREE_GENERATION_LIMIT


# =============================================================================
# СТАТИСТИКА И АНАЛИТИКА
# =============================================================================

async def get_total_users_count() -> int:
    """Возвращает общее количество пользователей."""
    async with async_session() as session:
        return await session.scalar(select(func.count(User.id))) or 0


async def get_questions_count_by_period(start_date: datetime, end_date: datetime) -> int:
    """Возвращает количество вопросов за указанный период."""
    async with async_session() as session:
        return (
            await session.scalar(
                select(func.count(QuizQuestion.id)).where(
                    and_(
                        QuizQuestion.generated_at >= start_date,
                        QuizQuestion.generated_at < end_date,
                    )
                )
            )
            or 0
        )


async def get_global_token_stats(
    user_id: Optional[int] = None, days: Optional[int] = None
) -> Dict[str, int]:
    """Возвращает статистику по использованию токенов."""
    async with async_session() as session:
        filters = []
        if user_id is not None:
            filters.append(QuizQuestion.user_id == user_id)
        if days is not None:
            filters.append(QuizQuestion.generated_at >= datetime.now() - timedelta(days=days))

        stmt = select(
            func.sum(QuizQuestion.gen_total_tokens).label("gen"),
            func.sum(QuizQuestion.eval_total_tokens).label("eval"),
        )
        if filters:
            stmt = stmt.where(and_(*filters))

        res = (await session.execute(stmt)).one_or_none()
        gen = int(res.gen or 0) if res else 0
        eval_tokens = int(res.eval or 0) if res else 0

        return {"generation": gen, "evaluation": eval_tokens, "total": gen + eval_tokens}


async def get_users_paginated(limit: int, offset: int) -> List[int]:
    """Возвращает список Telegram ID пользователей с пагинацией."""
    async with async_session() as session:
        result = await session.execute(
            select(User.user_id).order_by(User.id.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())


async def get_users_for_reminders() -> List[int]:
    """Возвращает список ID пользователей с включёнными напоминаниями."""
    async with async_session() as session:
        result = await session.execute(select(User.user_id).where(User.reminders == 1))
        return list(result.scalars().all())


async def get_daily_summary_data() -> Dict[str, Any]:
    """
    Возвращает агрегированную аналитическую сводку для админа.

    Returns:
        dict с данными о пользователях и статистике за вчера/сегодня
    """
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0

        now = datetime.now()
        today_start = datetime.combine(now.date(), time.min)
        yesterday_start = today_start - timedelta(days=1)

        # Статистика за вчера
        yesterday_stmt = select(
            func.count(QuizQuestion.id).label("cnt"),
            func.sum(QuizQuestion.gen_total_tokens).label("gen"),
            func.sum(QuizQuestion.eval_total_tokens).label("eval"),
        ).where(
            and_(
                QuizQuestion.generated_at >= yesterday_start,
                QuizQuestion.generated_at < today_start,
            )
        )
        y_res = (await session.execute(yesterday_stmt)).one_or_none()

        # Статистика за сегодня
        today_stmt = select(
            func.count(QuizQuestion.id).label("cnt"),
            func.sum(QuizQuestion.gen_total_tokens).label("gen"),
            func.sum(QuizQuestion.eval_total_tokens).label("eval"),
        ).where(QuizQuestion.generated_at >= today_start)
        t_res = (await session.execute(today_stmt)).one_or_none()

        def safe_int(value: Any) -> int:
            return int(value or 0)

        return {
            "total_users": total_users,
            "yesterday": {
                "questions": y_res.cnt if y_res else 0,
                "gen_tokens": safe_int(y_res.gen if y_res else None),
                "eval_tokens": safe_int(y_res.eval if y_res else None),
                "total_tokens": safe_int(y_res.gen if y_res else None)
                + safe_int(y_res.eval if y_res else None),
            },
            "today": {
                "questions": t_res.cnt if t_res else 0,
                "gen_tokens": safe_int(t_res.gen if t_res else None),
                "eval_tokens": safe_int(t_res.eval if t_res else None),
                "total_tokens": safe_int(t_res.gen if t_res else None)
                + safe_int(t_res.eval if t_res else None),
            },
        }


async def get_user_analytics_data(user_id: int, days: Optional[int] = None) -> Dict[str, Any]:
    """
    Возвращает агрегированную аналитику по вопросам викторины.
    """
    async with async_session() as session:
        base_filters = [QuizQuestion.user_id == user_id]

        if days is not None:
            start_date = datetime.now() - timedelta(days=days)
            base_filters.append(QuizQuestion.generated_at >= start_date)

        # Общая статистика
        stats_stmt = (
            select(
                func.count(QuizQuestion.id).label("total"),
                func.avg(QuizQuestion.rating).label("avg_rating"),
                func.sum(case((QuizQuestion.correctness == "правильно", 1), else_=0)).label("correct"),
                func.sum(case((QuizQuestion.correctness == "частично", 1), else_=0)).label("partial"),
                func.sum(case((QuizQuestion.correctness == "неправильно", 1), else_=0)).label("wrong"),
            )
            .where(*base_filters)
        )
        stats_result = await session.execute(stats_stmt)
        stats_row = stats_result.one_or_none()

        # Топ-3 файлов
        top_files_stmt = (
            select(QuizQuestion.source_file, func.count(QuizQuestion.id).label("cnt"))
            .where(*base_filters)
            .group_by(QuizQuestion.source_file)
            .order_by(desc("cnt"))
            .limit(3)
        )
        top_files_result = await session.execute(top_files_stmt)
        top_files = [(row.source_file, row.cnt) for row in top_files_result.all()]

        # Динамика по дням
        limit_days = min(days, 7) if days else 7
        timeline_start = datetime.now() - timedelta(days=limit_days)

        daily_stmt = (
            select(
                func.date(QuizQuestion.generated_at).label("day"),
                func.count(QuizQuestion.id).label("cnt"),
                func.avg(QuizQuestion.rating).label("avg_r"),
            )
            .where(QuizQuestion.user_id == user_id, QuizQuestion.generated_at >= timeline_start)
            .group_by(func.date(QuizQuestion.generated_at))
            .order_by(func.date(QuizQuestion.generated_at))
        )
        daily_result = await session.execute(daily_stmt)
        daily_data = [(row.day, row.cnt, row.avg_r) for row in daily_result.all()]

        return {
            "total": stats_row.total if stats_row else 0,
            "avg_rating": round(stats_row.avg_rating, 2) if stats_row and stats_row.avg_rating else 0.0,
            "correct": stats_row.correct if stats_row and stats_row.correct else 0,
            "partial": stats_row.partial if stats_row and stats_row.partial else 0,
            "wrong": stats_row.wrong if stats_row and stats_row.wrong else 0,
            "top_files": top_files,
            "daily": daily_data,
        }


# =============================================================================
# ЭКСПОРТ ДАННЫХ
# =============================================================================

async def get_user_quiz_export_data_list(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """
    Возвращает результаты викторин пользователя для экспорта в Excel.
    """
    start_date = datetime.now() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(
            select(QuizQuestion)
            .where(
                and_(
                    QuizQuestion.user_id == user_id,
                    QuizQuestion.generated_at >= start_date,
                )
            )
            .order_by(QuizQuestion.generated_at.desc())
        )
        questions = result.scalars().all()

        return [
            {
                "generated_at": q.generated_at.strftime("%Y-%m-%d %H:%M:%S") if q.generated_at else "",
                "source_file": q.source_file,
                "question": q.question,
                "correct_answer": q.correct_answer,
                "user_answer": q.user_answer,
                "correctness": q.correctness,
                "rating": q.rating or 0,
                "feedback": q.feedback or "",
                "gen_tokens": q.gen_total_tokens or 0,
                "eval_tokens": q.eval_total_tokens or 0,
            }
            for q in questions
        ]