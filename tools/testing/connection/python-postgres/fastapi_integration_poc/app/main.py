from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.database import engine, Base
from app.routers import users

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: Dispose engine
    await engine.dispose()

app = FastAPI(title="Modern FastAPI-SQLAlchemy PoC", lifespan=lifespan)

app.include_router(users.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Modern Stack PoC"}
