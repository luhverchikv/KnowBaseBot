# Используем легкую версию Python
FROM python:3.10-slim

# 🛠 Устанавливаем системные зависимости (ffmpeg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Переменные окружения для оптимизации Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта в контейнер
COPY . .

# Создаем папки для базы данных и логов, если их нет (на всякий случай)
RUN mkdir -p database logs

# Команда запуска бота
CMD ["python", "main.py"]

