import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./test.db"
SYNC_DATABASE_URL = "sqlite:///./test.db"

# Async engine & session for FastAPI backend
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine & session for Streamlit frontend
sync_engine = create_engine(SYNC_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_async_session():
    async with AsyncSessionLocal() as session:
        yield session