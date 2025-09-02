FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для кэша и загружаем модель от root
RUN mkdir -p /app/whisper-cache && \
    chmod 777 /app/whisper-cache && \
    WHISPER_CACHE_DIR=/app/whisper-cache python -c "import whisper; whisper.load_model('large')"

COPY . .

RUN useradd -m -u 1000 calls && chown -R calls:calls /app
USER calls

# Устанавливаем переменную окружения для кэша
ENV WHISPER_CACHE_DIR=/app/whisper-cache

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
