import time

from sqlmodel import create_engine, SQLModel, Session, text
from psycopg2 import OperationalError
from contextlib import contextmanager, AbstractContextManager
from classes.logger import Logger

from classes.settings import settings
from database.migrations import MigrationManager

MAX_RETRIES = 3
RETRY_DELAY = 0.3

# IMPORT MODELS #



class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(str(settings.database_url))

        # Создаем таблицы только в dev/test режиме
        if MigrationManager.is_development():
            # self._create_tables()
            pass

    def _create_tables(self):
        """Создание таблиц (только для dev/test)"""
        try:
            SQLModel.metadata.create_all(self.engine)
            Logger.info("⏭️ Таблицы созданы (режим разработки)")
        except Exception as e:
            Logger.err(f"⏭️ Ошибка при создании таблиц: {e}")
            raise

    @contextmanager
    def write_session(self, expire_on_commit: bool = False) -> AbstractContextManager[Session]:
        session = None
        for attempt in range(MAX_RETRIES):
            try:
                session = Session(self.engine, expire_on_commit=expire_on_commit)
                yield session
                session.commit()
                break
            except OperationalError as e:
                Logger.warn(f"Ошибка PostgreSQL (попытка {attempt + 1}/{MAX_RETRIES}): {e}")
                if session:
                    session.rollback()
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise
            finally:
                if session:
                    session.close()


db_manager = DatabaseManager()
write_session = db_manager.write_session
