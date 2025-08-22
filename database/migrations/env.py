from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel
from alembic import context
from classes.settings import settings
import logging

import database.entities_imports

'''
    Создание
    alembic revision -m "Описание миграции" — создаёт файл миграции с пустыми методами upgrade() и downgrade().
    alembic revision --autogenerate -m "Описание изменений" — автоматически определяет изменения в моделях SQLAlchemy.
    alembic revision --head-only -m "Описание" — создаёт миграцию только с обновлением версии.

    Применение
    alembic upgrade head — применить все миграции до последней версии.
    alembic upgrade +1 — применить следующую миграцию.
    alembic upgrade <revision_id> — применить конкретную миграцию.

    Откат
    alembic downgrade -1 — откатить последнюю миграцию.
    alembic downgrade base — откатить все миграции.
    alembic downgrade <revision_id> — откатить до конкретной ревизии.

    Список
    alembic current — показать текущую версию схемы.
    alembic history — показать историю всех миграций.
    alembic heads — показать все активные точки миграций.
    alembic show <revision_id> — показать содержимое конкретной миграции.
    alembic stamp head — пометить базу как соответствующую последней версии.

'''

# 1. Отключаем стандартное логирование Alembic
logging.getLogger('alembic').handlers.clear()
logging.getLogger('alembic').propagate = False  # Важно!

# 2. Инициализируем ваш логгер
logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)

# Очищаем все предыдущие обработчики
logger.handlers.clear()

# Настраиваем форматтер как вам нужно
formatter = logging.Formatter(
    fmt="%(levelname)s %(asctime)s [%(threadName)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Добавляем консольный обработчик
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


# 3. Перехватываем логи Alembic в ваш логгер
class AlembicProxyHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Перенаправляем логи Alembic в ваш логгер
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            logger.error(msg)
        elif record.levelno >= logging.WARNING:
            logger.warning(msg)
        elif record.levelno >= logging.INFO:
            logger.info(msg)
        else:
            logger.debug(msg)


# Применяем наш перехватчик
alembic_logger = logging.getLogger('alembic')
alembic_logger.handlers.clear()
alembic_logger.addHandler(AlembicProxyHandler())
alembic_logger.propagate = False

# 4. Отключаем fileConfig если он вам не нужен
config = context.config
if config.config_file_name is not None:
    # Отключаем стандартную конфигурацию логирования
    config.attributes['configure_logger'] = False

print("Таблицы в метаданных:", list(SQLModel.metadata.tables.keys()))
target_metadata = SQLModel.metadata


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """

    # https://dev.to/mchawa/sqlmodel-alembic-tutorial-gc8
    url = str(settings.database_url)

    # url = config.get_main_option("sqlalchemy.url")
    naming_convention = {
        "ix": "ix_%(table_name)s_%(column_0_label)s",  # Added table_name for more uniqueness
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",  # Used constraint_name for check constraints
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Отключаем логирование SQLAlchemy через Alembic
        include_schemas=False,
        include_object=None,
        process_revision_directives=None,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # connectable = engine_from_config(
    #     config.get_section(config.config_ini_section, {}),
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )
    url = str(settings.database_url)
    connectable = engine_from_config(
        {
            'url': url
        },
        prefix="",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Аналогичные настройки как в offline
            include_schemas=False,
            include_object=None,
            process_revision_directives=None,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
