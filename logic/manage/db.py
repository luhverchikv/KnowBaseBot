# logic/manage/db.py
import sqlite3
import os
import random
from pathlib import Path
from typing import Optional, List, Tuple

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
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')
            
            # Индекс для ускорения запросов WHERE user_id = ?
            self.cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_quiz_user_id ON quiz_questions(user_id)'
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
                          feedback: Optional[str] = None) -> int:
        """Добавляет запись о вопросе/результате квиза."""
        with self.connection:
            self.cursor.execute('''
                INSERT INTO quiz_questions (
                    user_id, source_file, question, correct_answer, 
                    user_answer, correctness, rating, feedback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, source_file, question, correct_answer, user_answer, correctness, rating, feedback))
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

    def get_user_questions(self, user_id: int, limit: int = 50) -> List[Tuple]:
        self.cursor.execute('''
            SELECT id, generated_at, source_file, question, correct_answer, 
                   user_answer, correctness, rating, feedback
            FROM quiz_questions WHERE user_id = ? ORDER BY generated_at DESC LIMIT ?
        ''', (user_id, limit))
        return self.cursor.fetchall()

