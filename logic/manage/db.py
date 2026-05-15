# logic/manage/db.py
import sqlite3
import os
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


