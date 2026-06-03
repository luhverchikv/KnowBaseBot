# database/requests.py
from database.models import async_session, User, QuizQuestion, Feedback, File
from sqlalchemy import select, update, delete, func, update, case, desc, and_
import random
from datetime import datetime, time, timedelta
from logic.ai_connector import TokenUsage
from typing import List, Dict, Any, Tuple, Optional


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
        return result.scalar() or 0

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


async def get_user_analytics_data(user_id: int, days: int = None) -> Dict[str, Any]:
    """
    Асинхронно собирает агрегированную аналитику по вопросам викторины для пользователя.
    """
    async with async_session() as session:
        # Базовое условие фильтрации по ID пользователя
        base_filters = [QuizQuestion.user_id == user_id]
        
        # Если задан период в днях, рассчитываем стартовую дату
        if days is not None:
            start_date = datetime.now() - timedelta(days=days)
            base_filters.append(QuizQuestion.generated_at >= start_date)

        # 1. Запрос общих показателей и точности ответов
        # Используем конструкцию case() аналогично старому CASE WHEN в SQL
        stats_stmt = (
            select(
                func.count(QuizQuestion.id).label("total"),
                func.avg(QuizQuestion.rating).label("avg_rating"),
                func.sum(case((QuizQuestion.correctness == "правильно", 1), else_=0)).label("correct"),
                func.sum(case((QuizQuestion.correctness == "частично", 1), else_=0)).label("partial"),
                func.sum(case((QuizQuestion.correctness == "неправильно", 1), else_=0)).label("wrong")
            )
            .where(*base_filters)
        )
        stats_result = await session.execute(stats_stmt)
        stats_row = stats_result.one_or_none()

        # 2. Топ-3 файлов по активности генераций
        top_files_stmt = (
            select(
                QuizQuestion.source_file,
                func.count(QuizQuestion.id).label("cnt")
            )
            .where(*base_filters)
            .group_by(QuizQuestion.source_file)
            .order_by(desc("cnt"))
            .limit(3)
        )
        top_files_result = await session.execute(top_files_stmt)
        top_files = [(row.source_file, row.cnt) for row in top_files_result.all()]

        # 3. Динамика по дням (для отображения мини-графика за последние максимум 7 дней)
        limit_days = min(days, 7) if days else 7
        timeline_start = datetime.now() - timedelta(days=limit_days)
        
        # Функция func.date() извлекает только дату YYYY-MM-DD
        date_label = func.date(QuizQuestion.generated_at).label("day")
        
        daily_stmt = (
            select(
                date_label,
                func.count(QuizQuestion.id).label("cnt"),
                func.avg(QuizQuestion.rating).label("avg_r")
            )
            .where(QuizQuestion.user_id == user_id, QuizQuestion.generated_at >= timeline_start)
            .group_by(date_label)
            .order_by(date_label)
        )
        daily_result = await session.execute(daily_stmt)
        daily_data = [(row.day, row.cnt, row.avg_r) for row in daily_result.all()]

        return {
            'total': stats_row.total if stats_row else 0,
            'avg_rating': round(stats_row.avg_rating, 2) if stats_row and stats_row.avg_rating else 0.0,
            'correct': stats_row.correct if stats_row and stats_row.correct else 0,
            'partial': stats_row.partial if stats_row and stats_row.partial else 0,
            'wrong': stats_row.wrong if stats_row and stats_row.wrong else 0,
            'top_files': top_files,
            'daily': daily_data
        }



# --- 1. Функция для обычных напоминаний ---

async def get_users_for_reminders() -> List[int]:
    """Возвращает список ID всех пользователей, у которых включены напоминания (reminders=1)."""
    async with async_session() as session:
        result = await session.execute(
            select(User.user_id).where(User.reminders == 1)
        )
        return list(result.scalars().all())

# --- 2. Функции для утренней админ-аналитики ---

async def get_latest_unread_feedback(limit: int = 5) -> List[Dict[str, Any]]:
    """Возвращает список последних непрочитанных отзывов."""
    async with async_session() as session:
        # Предполагается, что в модели Feedback есть поле is_read (0 или 1 / False или True)
        # Если поле называется по-другому, скорректируйте фильтр
        stmt = (
            select(Feedback, User.user_id)
            .join(User, Feedback.user_id == User.user_id, isouter=True)
            .where(Feedback.is_read == 0)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        
        unread_list = []
        for row in result.all():
            fb = row[0]
            unread_list.append({
                'text': fb.feedback_text,
                'created_at': fb.created_at.strftime('%d.%m %H:%M') if fb.created_at else '',
                'tg_id': fb.user_id
            })
        return unread_list

async def get_daily_summary_data() -> Dict[str, Any]:
    """
    Асинхронно собирает общую аналитическую сводку для владельца бота
    (Всего юзеров, статистика за вчера и статистика за сегодня).
    """
    async with async_session() as session:
        # 1. Всего пользователей
        total_users = await session.scalar(select(func.count(User.id))) or 0

        # Временные границы для "вчера" и "сегодня"
        now = datetime.now()
        today_start = datetime.combine(now.date(), time.min)
        yesterday_start = today_start - timedelta(days=1)

        # 2. Агрегация за ВЧЕРА
        yesterday_stmt = select(
            func.count(QuizQuestion.id).label("cnt"),
            func.sum(QuizQuestion.gen_total_tokens).label("gen"),
            func.sum(QuizQuestion.eval_total_tokens).label("eval")
        ).where(and_(
            QuizQuestion.generated_at >= yesterday_start,
            QuizQuestion.generated_at < today_start
        ))
        y_res = (await session.execute(yesterday_stmt)).one_or_none()

        # 3. Агрегация за СЕГОДНЯ
        today_stmt = select(
            func.count(QuizQuestion.id).label("cnt"),
            func.sum(QuizQuestion.gen_total_tokens).label("gen"),
            func.sum(QuizQuestion.eval_total_tokens).label("eval")
        ).where(QuizQuestion.generated_at >= today_start)
        t_res = (await session.execute(today_stmt)).one_or_none()

        # Безопасно парсим значения (заменяем None на 0)
        y_questions = y_res.cnt if y_res else 0
        y_gen = int(y_res.gen or 0) if y_res else 0
        y_eval = int(y_res.eval or 0) if y_res else 0

        t_questions = t_res.cnt if t_res else 0
        t_gen = int(t_res.gen or 0) if t_res else 0
        t_eval = int(t_res.eval or 0) if t_res else 0

        return {
            'total_users': total_users,
            'yesterday': {
                'questions': y_questions,
                'gen_tokens': y_gen,
                'eval_tokens': y_eval,
                'total_tokens': y_gen + y_eval
            },
            'today': {
                'questions': t_questions,
                'gen_tokens': t_gen,
                'eval_tokens': t_eval,
                'total_tokens': t_gen + t_eval
            }
        }



# --- 1. Статистика и Счетчики ---

async def get_unread_feedback_count() -> int:
    """Возвращает количество непрочитанных отзывов."""
    async with async_session() as session:
        return await session.scalar(select(func.count(Feedback.id)).where(Feedback.is_read == 0)) or 0

async def get_total_users_count() -> int:
    """Возвращает общее количество пользователей."""
    async with async_session() as session:
        return await session.scalar(select(func.count(User.id))) or 0

async def get_questions_count_by_period(start_date: datetime, end_date: datetime) -> int:
    """Возвращает количество вопросов, сгенерированных за указанный период времени."""
    async with async_session() as session:
        stmt = select(func.count(QuizQuestion.id)).where(
            and_(QuizQuestion.generated_at >= start_date, QuizQuestion.generated_at < end_date)
        )
        return await session.scalar(stmt) or 0

async def get_global_token_stats(user_id: Optional[int] = None, days: Optional[int] = None) -> Dict[str, int]:
    """
    Возвращает статистику по использованию токенов.
    Если передан user_id — считает по конкретному пользователю.
    Если передан days — фильтрует за последние N дней.
    """
    async with async_session() as session:
        filters = []
        if user_id is not None:
            filters.append(QuizQuestion.user_id == user_id)
        if days is not None:
            start_date = datetime.now() - timedelta(days=days)
            filters.append(QuizQuestion.generated_at >= start_date)

        stmt = select(
            func.sum(QuizQuestion.gen_total_tokens).label("gen"),
            func.sum(QuizQuestion.eval_total_tokens).label("eval")
        )
        if filters:
            stmt = stmt.where(and_(*filters))

        res = (await session.execute(stmt)).one_or_none()
        gen = int(res.gen or 0) if res else 0
        eval_tokens = int(res.eval or 0) if res else 0

        return {
            "generation": gen,
            "evaluation": eval_tokens,
            "total": gen + eval_tokens
        }

# --- 2. Пользователи и Лимиты ---

async def get_users_paginated(limit: int, offset: int) -> List[int]:
    """Возвращает список Telegram ID пользователей с пагинацией."""
    async with async_session() as session:
        stmt = select(User.user_id).order_by(User.id.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

async def get_user_profile_counters(user_id: int) -> Tuple[int, int]:
    """Возвращает (количество_вопросов, количество_файлов) для конкретного пользователя."""
    async with async_session() as session:
        # Импортируйте модель File из database.models, если она там объявлена
        from database.models import File  
        
        q_count = await session.scalar(select(func.count(QuizQuestion.id)).where(QuizQuestion.user_id == user_id)) or 0
        f_count = await session.scalar(select(func.count(File.id)).where(File.user_id == user_id)) or 0
        return q_count, f_count

async def get_user_limits_dict(user_id: int) -> Dict[str, Any]:
    """Возвращает лимиты пользователя в виде словаря."""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.user_id == user_id))
        if not user:
            return {"max_questions_per_day": 0, "max_files": 0, "max_file_size_mb": 0.0}
        
        return {
            "max_questions_per_day": getattr(user, "max_questions_per_day", 20),
            "max_files": getattr(user, "max_files", 5),
            "max_file_size_mb": getattr(user, "max_file_size_mb", 10.0)
        }

async def update_user_limit_value(user_id: int, field: str, value: Any) -> bool:
    """Обновляет указанный лимит пользователя."""
    async with async_session() as session:
        stmt = update(User).where(User.user_id == user_id).values({field: value})
        await session.execute(stmt)
        await session.commit()
        return True

# --- 3. Отзывы ---

async def get_feedback_paginated(limit: int, offset: int) -> List[Tuple[int, int, str, str, int]]:
    """Возвращает пагинированный список отзывов вместе с Telegram ID пользователя."""
    async with async_session() as session:
        stmt = (
            select(
                Feedback.id, 
                Feedback.user_id, 
                Feedback.feedback_text, 
                Feedback.created_at, 
                User.user_id.label("tg_id")
            )
            .join(User, Feedback.user_id == User.user_id, isouter=True)
            .order_by(Feedback.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        
        feedbacks = []
        for row in result.all():
            created_str = row.created_at.strftime("%d.%m.%Y %H:%M") if row.created_at else ""
            feedbacks.append((row.id, row.user_id, row.feedback_text, created_str, row.tg_id))
        return feedbacks

async def get_feedback_by_id(fb_id: int) -> Optional[Tuple[int, str, str, int]]:
    """Возвращает детальную информацию об отзыве."""
    async with async_session() as session:
        fb = await session.scalar(select(Feedback).where(Feedback.id == fb_id))
        if fb:
            created_str = fb.created_at.strftime("%d.%m.%Y %H:%M") if fb.created_at else ""
            # Возвращаем в том же порядке: user_id, feedback_text, created_at, is_read
            is_read_val = 1 if fb.is_read else 0
            return fb.user_id, fb.feedback_text, created_str, is_read_val
        return None

async def mark_feedback_read(fb_id: int) -> None:
    """Помечает отзыв как прочитанный."""
    async with async_session() as session:
        await session.execute(update(Feedback).where(Feedback.id == fb_id).values(is_read=1))
        await session.commit()

async def delete_feedback_by_id(fb_id: int) -> bool:
    """Удаляет отзыв из базы данных."""
    async with async_session() as session:
        await session.execute(delete(Feedback).where(Feedback.id == fb_id))
        await session.commit()
        return True

# --- 4. Экспорт ---
async def get_user_quiz_export_data_list(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Получает результаты викторин пользователя за последние N дней для экспорта в Excel."""
    async with async_session() as session:
        start_date = datetime.now() - timedelta(days=days)
        stmt = (
            select(QuizQuestion)
            .where(and_(QuizQuestion.user_id == user_id, QuizQuestion.generated_at >= start_date))
            .order_by(QuizQuestion.generated_at.desc())
        )
        result = await session.execute(stmt)
        questions = result.scalars().all()

        data_list = []
        for q in questions:
            data_list.append({
                "generated_at": q.generated_at.strftime("%Y-%m-%d %H:%M:%S") if q.generated_at else "",
                "source_file": q.source_file,
                "question": q.question,
                "correct_answer": q.correct_answer,
                "user_answer": q.user_answer,
                "correctness": q.correctness,
                "rating": q.rating or 0,
                "feedback": q.feedback or "",
                "gen_tokens": q.gen_total_tokens or 0,
                "eval_tokens": q.eval_total_tokens or 0
            })
        return data_list