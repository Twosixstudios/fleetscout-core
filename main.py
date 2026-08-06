from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.core.database import Base, engine, AsyncSessionLocal
from src.core.models import User, Vehicle, Load  # Register models with SQLAlchemy

from src.api.auth import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: (re)build the database schema
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    yield
    # Shutdown: close the database here if needed


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["Health Check"])
async def read_root():
    return {"status": "healthy"}

app.include_router(router, prefix="/api/auth", tags=["auth"])