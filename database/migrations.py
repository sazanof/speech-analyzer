# database/migrations.py
import os
from alembic.config import Config
from alembic import command
from typing import Optional

from classes.logger import Logger
from classes.settings import  settings


class MigrationManager:

    @staticmethod
    def is_development() -> bool:
        """Определяем нужно ли запускать миграции"""
        return settings.APP_MODE.lower() in ("development", "test")

    @staticmethod
    def should_run_migrations() -> bool:
        """Определяем нужно ли запускать миграции"""
        if settings.APP_MODE.lower() != "production":
            Logger.debug("⏭️ Skipping migrations in non-production mode")
            return False
        return True

    @staticmethod
    def get_alembic_config(config_path: Optional[str] = None) -> Config:
        """Создаем конфиг Alembic с учетом настроек приложения"""
        alembic_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = config_path or os.path.join(alembic_dir, "alembic.ini")

        alembic_cfg = Config(config_path)
        # Переопределяем URL из настроек приложения
        alembic_cfg.set_main_option("sqlalchemy.url", str(settings.database_url))
        return alembic_cfg

    @classmethod
    def run_migrations(cls):
        if not cls.should_run_migrations():
            return

        try:
            Logger.info("⏭️ Starting database migrations...")
            alembic_cfg = cls.get_alembic_config()
            command.upgrade(alembic_cfg, "head")
            Logger.info("⏭️ Migrations completed successfully")
        except Exception as e:
            Logger.err(f"⏭️ Migration failed: {e}")
            # Дополнительные действия при ошибке
            cls.on_migration_failure(e)
            raise

    @staticmethod
    def on_migration_failure(error: Exception):
        """Действия при неудачной миграции"""
        # Здесь можно добавить нотификации, откат и т.д.
        pass
