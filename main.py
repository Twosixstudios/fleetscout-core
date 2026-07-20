from fastapi import FastAPI, Request
from src.core.database import Base, engine, AsyncSessionLocal
from src.core.models import User, Vehicle, Load  # Register models with SQLAlchemy

from src.api.auth import router

app = FastAPI()
app.include_router(router)

# Define the startup function
async def on_startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Error during startup: {e}")
        exit(1)

# Define the shutdown function
async def on_shutdown():
    pass  # Implement the actual logic to close the database here

@app.middleware("http")
async def lifespan(request: Request, call_next):
    if request.method == "GET" and request.url.path == "/health":
        await on_startup()
    response = await call_next(request)
    return response

# Register startup and shutdown events
app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)

@app.get("/health", tags=["Health Check"])
async def read_root():
    return {"status": "healthy"}

app.include_router(router, prefix="/api/auth", tags=["auth"])