# logic/manage/db.py

import sqlite3
import os
from typing import Optional, List, Dict, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from logic.ai_connector import TokenUsage


class TokenUsage:
    """Dataclass для хранения информации о токенах"""
    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class Database:
    def __init__(self, path_to_database='database/database.db'):
        # Создаём директорию, если её нет
        os.makedirs(os.path.dirname(path_to_database), exist_ok=True)

        self.path_to_database = path_to_database
        self.connection = sqlite3.connect(path_to_database, check_same_thread=False)
        self.cursor = self.connection.cursor()

        # Включаем проверку внешних ключей
        self.cursor.execute("PRAGMA foreign_keys = ON")

        # Миграция: добавляем колонку max_file_size_mb если её нет
        self._migrate_add_max_file_size_mb()

        self._create_tables()

    def _migrate_add_max_file_size_mb(self) -> None:
        """Добавляет колонку max_file_size_mb в таблицу users если её нет."""
        try:
            self.cursor.execute("SELECT max_file_size_mb FROM users LIMIT 1")
        except sqlite3.OperationalError:
            # Колонки нет — добавляем
            self.cursor.execute("ALTER TABLE users ADD COLUMN max_file_size_mb REAL NOT NULL DEFAULT 0.25")
            self.connection.commit()

    def _create_tables(self) -> None:
        """Создание всех необходимых таблиц"""
        with self.connection:
            # Таблица пользователей
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    max_files INTEGER NOT NULL DEFAULT 3,
                    max_file_size_mb REAL NOT NULL DEFAULT 0.25,
                    max_questions_per_day INTEGER NOT NULL DEFAULT 3,
                    reminders INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица для хранения файлов базы знаний
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT,
                    content_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

            # Таблица для вопросов и ответов с полями для токенов
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS quiz_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    file_id INTEGER,
                    source_file TEXT NOT NULL DEFAULT '',
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    user_answer TEXT,
                    correctness TEXT CHECK (correctness IN ('правильно','частично','неправильно')),
                    rating INTEGER CHECK (rating BETWEEN 0 AND 5),
                    feedback TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    -- ✅ Поля для токенов генерации вопросов
                    gen_prompt_tokens INTEGER DEFAULT 0,
                    gen_completion_tokens INTEGER DEFAULT 0,
                    gen_total_tokens INTEGER DEFAULT 0,
                    -- ✅ Поля для токенов оценки ответов
                    eval_prompt_tokens INTEGER DEFAULT 0,
                    eval_completion_tokens INTEGER DEFAULT 0,
                    eval_total_tokens INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (file_id) REFERENCES knowledge_files(id)
                )
            ''')

            # Таблица для отзывов
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

            # Индекс для ускорения запросов
            self.cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_quiz_user_id ON quiz_questions(user_id)'
            )

    def user_exists(self, user_id: int) -> bool:
        """Проверяет, существует ли пользователь в базе"""
        self.cursor.execute(
            'SELECT 1 FROM users WHERE user_id = ?',
            (user_id,)
        )
        return self.cursor.fetchone() is not None

    def add_user(self, user_id: int) -> None:
        """Добавляет нового пользователя в базу"""
        with self.connection:
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (user_id) VALUES (?)
            ''', (user_id,))

    def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает настройки пользователя"""
        self.cursor.execute('''
            SELECT max_files, max_questions_per_day, reminders
            FROM users WHERE user_id = ?
        ''', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'max_files': row[0],
                'max_questions_per_day': row[1],
                'reminders': row[2]
            }
        return None

    def get_user_max_files(self, user_id: int) -> int:
        """Возвращает максимальное количество файлов для пользователя"""
        self.cursor.execute("SELECT max_files FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 3

    def update_user_setting(self, user_id: int, setting: str, value: Any) -> None:
        """Обновляет настройку пользователя"""
        allowed_settings = ['max_files', 'max_questions_per_day', 'reminders']
        if setting not in allowed_settings:
            raise ValueError(f"Недопустимая настройка: {setting}")

        with self.connection:
            self.cursor.execute(
                f'UPDATE users SET {setting} = ? WHERE user_id = ?',
                (value, user_id)
            )

    def add_knowledge_file(self, user_id: int, file_name: str,
                           file_path: str, file_type: str = None,
                           content_text: str = None) -> int:
        """Добавляет файл в базу знаний пользователя"""
        with self.connection:
            self.cursor.execute('''
                INSERT INTO knowledge_files
                (user_id, file_name, file_path, file_type, content_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, file_name, file_path, file_type, content_text))
            return self.cursor.lastrowid

    def get_user_files(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает все файлы пользователя"""
        self.cursor.execute('''
            SELECT id, file_name, file_path, file_type, created_at
            FROM knowledge_files WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        return [
            {
                'id': row[0],
                'file_name': row[1],
                'file_path': row[2],
                'file_type': row[3],
                'created_at': row[4]
            }
            for row in self.cursor.fetchall()
        ]

    def delete_knowledge_file(self, file_id: int, user_id: int) -> bool:
        """Удаляет файл из базы знаний"""
        with self.connection:
            cursor = self.cursor.execute(
                'DELETE FROM knowledge_files WHERE id = ? AND user_id = ?',
                (file_id, user_id)
            )
            return cursor.rowcount > 0

    def count_user_files(self, user_id: int) -> int:
        """Подсчитывает количество файлов пользователя"""
        self.cursor.execute(
            'SELECT COUNT(*) FROM knowledge_files WHERE user_id = ?',
            (user_id,)
        )
        return self.cursor.fetchone()[0]

    def add_quiz_question(self, user_id: int, question: str,
                         answer: str, file_id: int = None,
                         source_file: str = '',
                         gen_tokens: 'TokenUsage' = None) -> int:
        """Добавляет вопрос для викторины с токенами генерации"""
        with self.connection:
            self.cursor.execute('''
                INSERT INTO quiz_questions (user_id, file_id, source_file, question, answer,
                    gen_prompt_tokens, gen_completion_tokens, gen_total_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, file_id, source_file, question, answer,
                gen_tokens.prompt_tokens if gen_tokens else 0,
                gen_tokens.completion_tokens if gen_tokens else 0,
                gen_tokens.total_tokens if gen_tokens else 0
            ))
            return self.cursor.lastrowid

    def update_eval_tokens(self, question_id: int, tokens: 'TokenUsage') -> None:
        """Обновляет токены оценки для вопроса"""
        with self.connection:
            self.cursor.execute('''
                UPDATE quiz_questions
                SET eval_prompt_tokens = ?, eval_completion_tokens = ?, eval_total_tokens = ?
                WHERE id = ?
            ''', (tokens.prompt_tokens, tokens.completion_tokens, tokens.total_tokens, question_id))

    def get_token_stats(self, user_id: Optional[int] = None, days: int = None) -> dict:
        """Возвращает статистику токенов.
        Если user_id=None — агрегирует по всем пользователям.
        """
        user_filter = f"AND user_id = {user_id}" if user_id is not None else ""
        date_filter = f"AND DATE(created_at) >= DATE('now', '-{days} days')" if days else ""

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
        """Возвращает список user_id пользователей с пагинацией."""
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
        from pathlib import Path
        user_dir = Path("database") / str(user_id)
        if not user_dir.exists():
            return 0
        return sum(1 for f in user_dir.iterdir() if f.is_file() and f.suffix.lower() in {".md", ".markdown"})

    def get_user_limits(self, user_id: int) -> dict:
        """Возвращает текущие лимиты пользователя."""
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
            pass
        return {"max_files": 3, "max_file_size_mb": 0.25, "max_questions_per_day": 3}

    def update_user_limit(self, user_id: int, field: str, value) -> bool:
        """Обновляет один лимит пользователя."""
        allowed_fields = {'max_files', 'max_file_size_mb', 'max_questions_per_day'}
        if field not in allowed_fields:
            return False

        with self.connection:
            self.cursor.execute(
                f"UPDATE users SET {field} = ? WHERE user_id = ?",
                (value, user_id)
            )
            return self.cursor.rowcount > 0

    # ===================== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ =====================

    def get_user_questions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает вопросы пользователя для викторины"""
        self.cursor.execute('''
            SELECT id, question, answer, file_id, created_at
            FROM quiz_questions WHERE user_id = ?
            ORDER BY RANDOM() LIMIT ?
        ''', (user_id, limit))
        return [
            {
                'id': row[0],
                'question': row[1],
                'answer': row[2],
                'file_id': row[3],
                'created_at': row[4]
            }
            for row in self.cursor.fetchall()
        ]

    def add_feedback(self, user_id: int, message: str) -> int:
        """Добавляет отзыв пользователя"""
        with self.connection:
            self.cursor.execute('''
                INSERT INTO feedback (user_id, message) VALUES (?, ?)
            ''', (user_id, message))
            return self.cursor.lastrowid

    def update_quiz_result(self, question_id: int, user_answer: str,
                          correctness: str, feedback: str) -> None:
        """Обновляет результат ответа пользователя"""
        with self.connection:
            self.cursor.execute(
                "UPDATE quiz_questions SET user_answer=?, correctness=?, feedback=? WHERE id=?",
                (user_answer, correctness, feedback, question_id)
            )

    def update_quiz_rating(self, question_id: int, rating: int) -> None:
        """Обновляет рейтинг вопроса"""
        with self.connection:
            self.cursor.execute(
                "UPDATE quiz_questions SET rating=? WHERE id=?",
                (rating, question_id)
            )

    def get_daily_questions_count(self, user_id: int) -> int:
        """Количество вопросов за сегодня"""
        self.cursor.execute("""
            SELECT COUNT(*) FROM quiz_questions
            WHERE user_id = ? AND DATE(created_at) = DATE('now')
        """, (user_id,))
        return self.cursor.fetchone()[0]

    def get_max_questions_per_day(self, user_id: int) -> int:
        """Максимальное количество вопросов в день"""
        self.cursor.execute(
            "SELECT max_questions_per_day FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else 3

    def get_random_user_file(self, user_id: int) -> Optional[str]:
        """Возвращает случайный файл пользователя"""
        import random
        from pathlib import Path
        user_dir = Path("database") / str(user_id)
        if not user_dir.exists():
            return None
        files = [f.name for f in user_dir.iterdir()
                 if f.is_file() and f.suffix.lower() in ['.md', '.markdown']]
        return random.choice(files) if files else None

    def get_total_users_count(self) -> int:
        """Общее количество пользователей"""
        self.cursor.execute("SELECT COUNT(*) FROM users")
        return self.cursor.fetchone()[0]

    def get_questions_count_today(self) -> int:
        """Количество вопросов сгенерированных сегодня"""
        self.cursor.execute(
            "SELECT COUNT(*) FROM quiz_questions WHERE DATE(created_at) = DATE('now')"
        )
        return self.cursor.fetchone()[0]

    def get_questions_count_yesterday(self) -> int:
        """Количество вопросов сгенерированных вчера"""
        self.cursor.execute(
            "SELECT COUNT(*) FROM quiz_questions WHERE DATE(created_at) = DATE('now', '-1 day')"
        )
        return self.cursor.fetchone()[0]

    def close(self) -> None:
        """Закрывает соединение с базой данных"""
        self.connection.close()