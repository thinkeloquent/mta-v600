from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import URL
import os
from dotenv import load_dotenv

load_dotenv()

# Build URL using robust components pattern
# This demonstrates the fix for "nodename" errors
def get_async_database_url():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")
    
    if not host: host="localhost"

    # URL.create is the gold standard for handling special chars and driver specifics
    return URL.create(
        drivername="postgresql+asyncpg",
        username=user,
        password=password,
        host=host,
        port=port,
        database=dbname,
    )

DATABASE_URL = get_async_database_url()

# Create Async Engine
# Pass 'ssl' in connect_args if needed (e.g. for cloud providers)
ssl_mode = "disable" # Explicitly disable for dev/test to avoid "server refuses"
engine = create_async_engine(
    DATABASE_URL, 
    echo=True,
    connect_args={"ssl": ssl_mode} 
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False, # Important for Async
)

class Base(DeclarativeBase):
    pass
