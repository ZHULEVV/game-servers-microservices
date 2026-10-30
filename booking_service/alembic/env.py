from alembic import context
from sqlalchemy import engine_from_config, pool

from app.schemas import booking  # noqa: F401  (регистрирует таблицы в Base.metadata)
from app.schemas.base_schema import Base
from app.settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.postgres_url)
target_metadata = Base.metadata

connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.",
                                 poolclass=pool.NullPool)
with connectable.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
