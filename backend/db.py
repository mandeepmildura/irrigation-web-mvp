import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DEFAULT_SQLITE_URL = "sqlite:////var/data/irrigation_v2.db"

DATABASE_URL_ENV = os.getenv("DATABASE_URL")
if DATABASE_URL_ENV and DATABASE_URL_ENV.strip():
    DATABASE_URL = DATABASE_URL_ENV
    USING_SQLITE_FALLBACK = False
else:
    DATABASE_URL = DEFAULT_SQLITE_URL
    USING_SQLITE_FALLBACK = True

IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# Optional helper for local SQLite development
# Alembic migrations should be used for schema changes in all environments.
def create_sqlite_schema_if_needed():
    if IS_SQLITE:
        Base.metadata.create_all(bind=engine)


# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
