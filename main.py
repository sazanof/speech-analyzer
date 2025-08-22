from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Depends

from classes.logger import Logger
from database.migrations import MigrationManager
from dependencies.ip_auth import ip_whitelist_dependency
from middleware.ip_whitelist import IPWhitelistMiddleware
from routes.conversation import conversations
from routes.dictionaries import dictionaries
from routes.recordings import recordings
from routes.tags import tags

from database.database import db_manager
from classes.settings import settings
from threads.analyze_text_thread import TaskProcessor
from threads.recognize_record_thread import recognize_thread


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Только если используем Nuitka (проверка скомпилированного режима)
    MigrationManager.run_migrations()
    Logger.info('Generator lifespan at start of app')
    recognize_thread.start()

    # Инициализация обработчика задач
    analyze_text_processor = TaskProcessor(max_workers=4)
    analyze_text_processor.start_fetcher(interval=30)

    yield
    # Clean up the ML entities and release the resources
    Logger.info('Finish lifespan at end of app')


app = FastAPI(
    lifespan=lifespan,
    root_path=settings.API_ROOT
)

# Добавляем middleware если включена IP-фильтрация
if settings.ENABLE_IP_WHITELIST:
    app.add_middleware(IPWhitelistMiddleware)
    print(f"IP whitelist enabled. Allowed IPs: {settings.ALLOWED_IPS}")
else:
    print("IP whitelist is disabled")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whisper-api"}


app.include_router(recordings)
app.include_router(dictionaries)

app.include_router(conversations)
app.include_router(tags)

# your app code here

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
