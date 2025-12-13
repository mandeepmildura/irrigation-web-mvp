from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🔴 IMPORTANT
# Using persistent disk on Render
# This file path MUST match your Render disk mount
DB_URL = "sqlite:////var/data/irrigation.db"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
