# logic/manage/db.py

import sqlite3
import os

class Database:
    def __init__(self, path_to_database='database/database.db'):
        # Создаём директорию, если её нет
        os.makedirs(os.path.dirname(path_to_database), exist_ok=True)
        
        self.connection = sqlite3.connect(path_to_database)
        self.cursor = self.connection.cursor()

        with self.connection:
            self.cursor.execute(
                '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id INTEGER UNIQUE NOT NULL,
                max_files              INTEGER NOT NULL DEFAULT 3,
                max_questions_per_day  INTEGER NOT NULL DEFAULT 3,
                reminders              INTEGER NOT NULL DEFAULT 0
             )''')
            
    def user_exists(self, user_id: int) -> bool:
        """Проверяет, существует ли пользователь с таким user_id."""
        self.cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None

    def add_user(self, user_id: int) -> None:
        """Добавляет нового пользователя в базу данных."""
        with self.connection:  # автоматически вызывает commit()
            self.cursor.execute(
                "INSERT INTO users (user_id) VALUES (?)", 
                (user_id,)
            )