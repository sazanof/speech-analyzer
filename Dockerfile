FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория - это корень приложения
WORKDIR /app

# Копируем ВСЕ в корень /app (а не в /app/app/)
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Запускаем main.py который находится в корне
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]