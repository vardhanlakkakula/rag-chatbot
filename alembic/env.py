from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from backend.database.connection import Base
from backend.database.models import (
    User,
    Document,
    Conversation,
    Message
)

from dotenv import load_dotenv
import os


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# Alembic configuration
# ============================================================

config = context.config


# ============================================================
# Logging
# ============================================================

if config.config_file_name is not None:

    fileConfig(
        config.config_file_name
    )


# ============================================================
# SQLAlchemy metadata
# ============================================================

target_metadata = Base.metadata


# ============================================================
# Database URL
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)


if not DATABASE_URL:

    raise ValueError(
        "DATABASE_URL is not configured."
    )


# ============================================================
# Offline migrations
# ============================================================

def run_migrations_offline():

    context.configure(

        url=DATABASE_URL,

        target_metadata=target_metadata,

        literal_binds=True,

        dialect_opts={
            "paramstyle": "named"
        }
    )


    with context.begin_transaction():

        context.run_migrations()


# ============================================================
# Online migrations
# ============================================================

def run_migrations_online():

    configuration = (
        config.get_section(
            config.config_ini_section
        )
    )


    configuration[
        "sqlalchemy.url"
    ] = DATABASE_URL


    connectable = engine_from_config(

        configuration,

        prefix="sqlalchemy.",

        poolclass=pool.NullPool
    )


    with connectable.connect() as connection:

        context.configure(

            connection=connection,

            target_metadata=target_metadata,

            compare_type=True,

            compare_server_default=True
        )


        with context.begin_transaction():

            context.run_migrations()


# ============================================================
# Run migration
# ============================================================

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()