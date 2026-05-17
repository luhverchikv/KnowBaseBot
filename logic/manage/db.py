# logic/manage/db.py
import sqlite3
import os
import random
from pathlib import Path
from typing import Optional, List, Tuple
from utils.logger import logger


class Database:
    def __init__(self, path_to_database='database/database.db'):
        # Создаём директорию для БД, если её нет
        os.makedirs(os.path.dirname(path_to_database), exist_ok=True)
        
        self.connection = sqlite3.connect(path_to_database, check_same_thread=False)
        self.cursor = self.connection.cursor()
        
        # ⚠️ SQLite отключает проверку внешних ключей по умолчанию. Включаем явно.
        self.cursor.execute("PRAGMA foreign_keys = ON")

        with self.connection:
            # 1. Таблица пользователей
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id INTEGER UNIQUE NOT NULL,
                    max_files              INTEGER NOT NULL DEFAULT 3,
                     max_file_size_mb        REAL    NOT NULL DEFAULT 0.25,
                    max_questions_per_day  INTEGER NOT NULL DEFAULT 3,
                    reminders              INTEGER NOT NULL DEFAULT 0
                )
            ''')

            # 2. Единая таблица вопросов/результатов квиза
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS quiz_questions (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id        INTEGER NOT NULL,
                    generated_at   TEXT NOT NULL DEFAULT (datetime('now')),
                    source_file    TEXT NOT NULL,
                    question       TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    user_answer    TEXT,
                    correctness    TEXT CHECK (correctness IN ('правильно','частично','неправильно')),
                    rating         INTEGER CHECK (rating BETWEEN 0 AND 5),
                    feedback       TEXT,
                    -- ✅ Поля для токенов
                    gen_prompt_tokens    INTEGER DEFAULT 0,
                    gen_completion_tokens INTEGER DEFAULT 0,
                    gen_total_tokens     INTEGER DEFAULT 0,
                    eval_prompt_tokens   INTEGER DEFAULT 0,
                    eval_completion_tokens INTEGER DEFAULT 0,
                    eval_total_tokens    INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            # Индекс для ускорения запросов WHERE user_id = ?
            self.cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_quiz_user_id ON quiz_questions(user_id)'
            )
            
            
            # 3. Таблица отзывов
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    feedback_text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    is_read INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            self.cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id)'
            )
            self.cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at)'
            )




    # ===================== USERS =====================
    def user_exists(self, user_id: int) -> bool:
        """Проверяет, существует ли пользователь с таким user_id."""
        self.cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None

    def add_user(self, user_id: int) -> None:
        """Добавляет нового пользователя в базу данных."""
        with self.connection:
            self.cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))

    # ===================== QUIZ QUESTIONS =====================
    def add_quiz_question(self, user_id: int, source_file: str, question: str, 
                      correct_answer: str, user_answer: Optional[str] = None, 
                      correctness: Optional[str] = None, rating: Optional[int] = None, 
                      feedback: Optional[str] = None,
                      gen_tokens: Optional['TokenUsage'] = None) -> int:  # type: ignore
        with self.connection:
            self.cursor.execute('''
                INSERT INTO quiz_questions (
                    user_id, source_file, question, correct_answer,  
                    user_answer, correctness, rating, feedback,
                    gen_prompt_tokens, gen_completion_tokens, gen_total_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, source_file, question, correct_answer,
                user_answer, correctness, rating, feedback,
                gen_tokens.prompt_tokens if gen_tokens else 0,
                gen_tokens.completion_tokens if gen_tokens else 0,
                gen_tokens.total_tokens if gen_tokens else 0
            ))
            logger.info(f"💾 Saving gen_tokens: {gen_tokens}")
            return self.cursor.lastrowid
    


    def get_user_questions(self, user_id: int, limit: int = 50) -> List[Tuple]:
        """Возвращает последние N вопросов пользователя."""
        self.cursor.execute('''
            SELECT id, generated_at, source_file, question, correct_answer, 
                   user_answer, correctness, rating, feedback
            FROM quiz_questions 
            WHERE user_id = ? 
            ORDER BY generated_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        return self.cursor.fetchall()

    
    def get_user_max_files(self, user_id: int) -> int:
        """Возвращает максимальное количество файлов для пользователя."""
        self.cursor.execute("SELECT max_files FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 3  # 3 по умолчанию, если запись не найдена

    def get_random_user_file(self, user_id: int) -> Optional[str]:
        user_dir = Path("database") / str(user_id)
        if not user_dir.exists(): return None
        files = [f.name for f in user_dir.iterdir() if f.is_file() and f.suffix.lower() == '.md']
        return random.choice(files) if files else None

    def get_daily_questions_count(self, user_id: int) -> int:
        self.cursor.execute("""
            SELECT COUNT(*) FROM quiz_questions
            WHERE user_id = ? AND DATE(generated_at) = DATE('now')
        """, (user_id,))
        return self.cursor.fetchone()[0]

    def get_max_questions_per_day(self, user_id: int) -> int:
        self.cursor.execute("SELECT max_questions_per_day FROM users WHERE user_id = ?", (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else 3


    def update_quiz_result(self, question_id: int, user_answer: str, correctness: str, feedback: str) -> None:
        with self.connection:
            self.cursor.execute(
                "UPDATE quiz_questions SET user_answer=?, correctness=?, feedback=? WHERE id=?",
                (user_answer, correctness, feedback, question_id)
            )

    def update_quiz_rating(self, question_id: int, rating: int) -> None:
        with self.connection:
            self.cursor.execute("UPDATE quiz_questions SET rating=? WHERE id=?", (rating, question_id))


    def get_user_average_rating(self, user_id: int, days: int = None) -> float:
        """Средний рейтинг пользователя (опционально за период)."""
        where = f"AND DATE(generated_at) >= DATE('now', '-{days} days')" if days else ""
        self.cursor.execute(f"""
            SELECT AVG(rating) FROM quiz_questions 
            WHERE user_id = ? AND rating IS NOT NULL {where}
        """, (user_id,))
        result = self.cursor.fetchone()[0]
        return round(result, 2) if result else 0.0

    def get_correctness_distribution(self, user_id: int, days: int = None) -> dict:
        """Распределение ответов по типам (правильно/частично/неправильно)."""
        where = f"AND DATE(generated_at) >= DATE('now', '-{days} days')" if days else ""
        self.cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN correctness='правильно' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN correctness='частично' THEN 1 ELSE 0 END) as partial,
                SUM(CASE WHEN correctness='неправильно' THEN 1 ELSE 0 END) as wrong,
                COUNT(*) as total
            FROM quiz_questions 
            WHERE user_id = ? {where}
        """, (user_id,))
        row = self.cursor.fetchone()
        total = row[3] or 1  # избегаем деления на 0
        return {
            'correct_pct': round((row[0] or 0) / total * 100),
            'partial_pct': round((row[1] or 0) / total * 100),
            'wrong_pct': round((row[2] or 0) / total * 100),
            'total': total
        }

    def get_total_users_count(self) -> int:
        """Возвращает общее количество пользователей."""
        self.cursor.execute("SELECT COUNT(*) FROM users")
        return self.cursor.fetchone()[0]

    def get_questions_count_today(self) -> int:
        """Возвращает количество вопросов, сгенерированных сегодня."""
        self.cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE DATE(generated_at) = DATE('now')")
        return self.cursor.fetchone()[0]

    def get_questions_count_yesterday(self) -> int:
        """Возвращает количество вопросов, сгенерированных вчера."""
        self.cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE DATE(generated_at) = DATE('now', '-1 day')")
        return self.cursor.fetchone()[0]

    def update_eval_tokens(self, question_id: int, tokens: 'TokenUsage') -> None:  # type: ignore
        with self.connection:
            self.cursor.execute('''
                UPDATE quiz_questions 
                SET eval_prompt_tokens=?, eval_completion_tokens=?, eval_total_tokens=?
                WHERE id=?
            ''', (tokens.prompt_tokens, tokens.completion_tokens, tokens.total_tokens, question_id))

    
    def get_token_stats(self, user_id: Optional[int] = None, days: int = None) -> dict:
        """
        Возвращает статистику токенов.
        Если user_id=None — агрегирует по всем пользователям.
        """
        user_filter = f"AND user_id = {user_id}" if user_id is not None else ""
        date_filter = f"AND DATE(generated_at) >= DATE('now', '-{days} days')" if days else ""
        
        self.cursor.execute(f'''
            SELECT 
                COALESCE(SUM(gen_total_tokens), 0) as gen_total,
                COALESCE(SUM(eval_total_tokens), 0) as eval_total,
                COALESCE(SUM(gen_total_tokens + eval_total_tokens), 0) as grand_total
            FROM quiz_questions 
            WHERE 1=1 {user_filter} {date_filter}
        ''')
        row = self.cursor.fetchone()
        return {
            'generation': row[0] or 0,
            'evaluation': row[1] or 0,
            'total': row[2] or 0
        }
    
    def get_user_max_file_size(self, user_id: int) -> float:
        """Возвращает максимальный размер файла для пользователя в МБ."""
        self.cursor.execute("SELECT max_file_size_mb FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0.25
        
    def get_users_paginated(self, limit: int = 10, offset: int = 0) -> list[tuple]:
        """Возвращает список user_id пользователей с пагинацией, отсортированный по возрастанию."""
        self.cursor.execute("""
            SELECT user_id FROM users 
            ORDER BY user_id ASC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return self.cursor.fetchall()

    def get_user_total_questions(self, user_id: int) -> int:
        """Возвращает общее количество сгенерированных вопросов для пользователя."""
        self.cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()[0]

    def get_user_files_count(self, user_id: int) -> int:
        """Считает количество .md файлов в директории пользователя."""
        user_dir = Path("database") / str(user_id)
        if not user_dir.exists():
            return 0
        return sum(1 for f in user_dir.iterdir() if f.is_file() and f.suffix.lower() in {".md", ".markdown"})

    def get_user_limits(self, user_id: int) -> dict:
        """Возвращает текущие лимиты пользователя (безопасно для старых схем БД)."""
        try:
            self.cursor.execute(
                "SELECT max_files, max_file_size_mb, max_questions_per_day FROM users WHERE user_id = ?", 
                (user_id,)
            )
            row = self.cursor.fetchone()
            if row:
                return {
                    "max_files": row[0],
                    "max_file_size_mb": row[1],
                    "max_questions_per_day": row[2]
                }
        except sqlite3.OperationalError:
            # Если колонки max_file_size_mb ещё нет в БД, вернём дефолты
            pass
        return {"max_files": 3, "max_file_size_mb": 0.25, "max_questions_per_day": 3}
    

    def update_user_limit(self, user_id: int, field: str, value) -> bool:
        """
        Обновляет один лимит пользователя.
        :param field: имя поля ('max_files', 'max_file_size_mb', 'max_questions_per_day')
        :param value: новое значение
        :return: True при успехе
        """
        # Валидация имени поля (защита от SQL-инъекций)
        allowed_fields = {'max_files', 'max_file_size_mb', 'max_questions_per_day'}
        if field not in allowed_fields:
            return False
        
        with self.connection:
            self.cursor.execute(
                f"UPDATE users SET {field} = ? WHERE user_id = ?",
                (value, user_id)
            )
            return self.cursor.rowcount > 0
    
    
# ======== методы работы с отзывами =======
    def save_feedback(self, user_id: int, feedback_text: str) -> int:
        """Сохраняет отзыв пользователя."""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO feedback (user_id, feedback_text) VALUES (?, ?)",
                (user_id, feedback_text)
            )
            return self.cursor.lastrowid

    def get_feedback_paginated(self, limit: int = 10, offset: int = 0, only_unread: bool = False) -> list[tuple]:
        """Возвращает список отзывов с пагинацией."""
        filter_clause = "WHERE is_read = 0" if only_unread else ""
        self.cursor.execute(f'''
            SELECT f.id, f.user_id, f.feedback_text, f.created_at, u.user_id as tg_id
            FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            {filter_clause}
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return self.cursor.fetchall()

    def get_unread_feedback_count(self) -> int:
        """Считает количество непрочитанных отзывов."""
        self.cursor.execute("SELECT COUNT(*) FROM feedback WHERE is_read = 0")
        return self.cursor.fetchone()[0]

    def mark_feedback_read(self, feedback_id: int) -> None:
        """Помечает отзыв как прочитанный."""
        with self.connection:
            self.cursor.execute("UPDATE feedback SET is_read = 1 WHERE id = ?", (feedback_id,))

    def delete_feedback(self, feedback_id: int) -> bool:
        """Удаляет отзыв по ID."""
        with self.connection:
            self.cursor.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
            return self.cursor.rowcount > 0

