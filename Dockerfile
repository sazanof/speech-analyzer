# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости для Whisper и PostgreSQL
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY app/ ./app/
COPY alembic/ ./alembic/

# Создаем не-root пользователя для безопасности
RUN useradd -m -u 1000 calls && chown -R calls:calls /app
USER calls

# Открываем порт
EXPOSE 8000

# Запускаем приложение
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]