import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

def get_db_url():
    """Get from env or build from components. Returns URL with postgresql+asyncpg prefix."""
    env_url = os.getenv("DATABASE_URL")
    
    if env_url:
        # Normalize scheme
        if env_url.startswith("postgres://"):
            return "postgresql+asyncpg://" + env_url[11:]
        elif env_url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + env_url[13:]
        elif not env_url.startswith("postgresql+asyncpg://"):
             # Assuming standard postgresql:// logic or raw, try to fix
             pass
        # Proceed with env_url if valid or fallback below if empty
        return env_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")
    
    # Ensure host is valid
    if not host: 
        host = "localhost"
        
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"

async def main():
    print("="*60)
    print("SQLAlchemy + asyncpg Connection Test (Enhanced)")
    print("="*60)

    url = get_db_url()
    
    # Clean URL: remove query params if any for cleaner testing of overrides
    if url and "?" in url:
        clean_url = url.split("?")[0]
        print(f"Using clean URL for injection tests: {clean_url}")
    else:
        clean_url = url

    print(f"Config:")
    print(f"  Target URL: {url}")
    print(f"  Clean URL: {clean_url}")

    # ---------------------------------------------------------
    # Test 1: Using URL directly
    # ---------------------------------------------------------
    print("\n[Test 1] Using URL directly")
    if url:
        try:
            engine = create_async_engine(url)
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT version()"))
                print(f"  SUCCESS: Connected! Version: {result.scalar()[:50]}...")
            await engine.dispose()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED (No URL)")

    # ---------------------------------------------------------
    # Test 2: Using Clean URL + connect_args={"ssl": "disable"}
    # ---------------------------------------------------------
    print("\n[Test 2] Using URL + connect_args={'ssl': 'disable'}")
    if clean_url:
        try:
            engine = create_async_engine(
                clean_url,
                connect_args={"ssl": "disable"}
            )
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                print(f"  SUCCESS: Connected!")
            await engine.dispose()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED")

    # ---------------------------------------------------------
    # Test 3: Using Clean URL + connect_args={"ssl": False}
    # ---------------------------------------------------------
    print("\n[Test 3] Using URL + connect_args={'ssl': False}")
    if clean_url:
        try:
            engine = create_async_engine(
                clean_url,
                connect_args={"ssl": False}
            )
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                print(f"  SUCCESS: Connected!")
            await engine.dispose()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED")

    # ---------------------------------------------------------
    # Test 4: Constructed explicitly (Host check)
    # ---------------------------------------------------------
    print("\n[Test 4] Explicit Construction (Check Host)")
    
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")
    
    constructed = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    print(f"  Constructed: {constructed.replace(':'+password, ':***')}")
    
    try:
        engine = create_async_engine(
            constructed,
            connect_args={"ssl": "disable"}
        )
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"  SUCCESS: Connected!")
        await engine.dispose()
    except Exception as e:
        print(f"  FAILURE: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
