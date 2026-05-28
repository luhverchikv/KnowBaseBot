Методы класса `Database`

### 📌 Управление пользователями

| Метод                   | Описание               | Параметры             |
| ----------------------- | ---------------------- | --------------------- |
| `user_exists()`         | Проверка существования | `user_id`             |
| `add_user()`            | Добавление нового      | `user_id`             |
| `get_user_difficulty()` | Получить сложность     | `user_id`             |
| `set_user_difficulty()` | Установить сложность   | `user_id, difficulty` |

### 📌 Работа с лимитами

| Метод | Описание |
|-------|----------|
| `get_user_max_files()` | Макс. количество файлов |
| `get_user_max_file_size()` | Макс. размер файла (МБ) |
| `get_max_questions_per_day()` | Макс. вопросов/день |
| `get_daily_questions_count()` | Вопросов за сегодня |
| `get_user_limits()` | Все лимиты (dict) |
| `update_user_limit()` | Обновить лимит |

### 📌 Статистика квизов

| Метод | Описание |
|-------|----------|
| `add_quiz_question()` | Сохранить вопрос |
| `update_quiz_result()` | Обновить результат |
| `update_quiz_rating()` | Обновить оценку |
| `get_user_questions()` | Последние N вопросов |
| `get_user_average_rating()` | Средний рейтинг |
| `get_correctness_distribution()` | % правильно/частично/неправильно |
| `get_user_total_questions()` | Всего вопросов |

### 📌 Токены и статистика

| Метод | Описание |
|-------|----------|
| `update_eval_tokens()` | Сохранить токены оценки |
| `get_token_stats()` | Статистика токенов (все/пользователя/период) |
| `get_token_stats_by_date()` | Статистика за конкретную дату |
| `get_total_users_count()` | Всего пользователей |
| `get_questions_count_today()` | Вопросов сегодня |
| `get_questions_count_yesterday()` | Вопросов вчера |
| `get_daily_summary()` | Сводка за сегодня/вчера |

### 📌 Работа с файлами

| Метод | Описание |
|-------|----------|
| `get_random_user_file()` | Случайный .md файл пользователя |
| `get_user_files_count()` | Количество файлов |

### 📌 Отзывы

| Метод | Описание |
|-------|----------|
| `save_feedback()` | Сохранить отзыв |
| `get_feedback_paginated()` | Список с пагинацией |
| `get_unread_feedback_count()` | Непрочитанных |
| `mark_feedback_read()` | Пометить прочитанным |
| `delete_feedback()` | Удалить отзыв |

### 📌 Напоминания

| Метод | Описание |
|-------|----------|
| `get_user_reminders()` | Статус напоминаний |
| `set_user_reminders()` | Включить/выключить |
| `get_users_by_reminders()` | Пользователи с напоминаниями |

### 📌 Экспорт| Метод | Описание |
|-------|----------|
| `get_user_quiz_export_data()` | Данные для Excel-отчёта |
---
