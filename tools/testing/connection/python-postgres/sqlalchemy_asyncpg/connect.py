import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def main():
    print("="*60)
    print("SQLAlchemy + asyncpg Connection Test")
    print("="*60)

    # Need postgresql+asyncpg:// scheme
    base_url = os.getenv("DATABASE_URL")
    
    # Ensure correct driver in URL if testing URL directly
    if base_url and not base_url.startswith("postgresql+asyncpg://"):
        # Just a Helper: Convert postgres:// or postgresql:// to postgresql+asyncpg://
        print(f"NOTE: Converting URL scheme to postgresql+asyncpg:// for test")
        if base_url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + base_url[11:]
        elif base_url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + base_url[13:]
        else:
            url = base_url
    else:
        url = base_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    # Clean URL: remove query params if any for cleaner testing of overrides
    if url and "?" in url:
        clean_url = url.split("?")[0]
        print(f"Using clean URL for injection tests: {clean_url}")
    else:
        clean_url = url

    print(f"Config:")
    print(f"  URL: {url}")
    print(f"  Clean URL: {clean_url}")
    print(f"  Host: {host}:{port}")

    # ---------------------------------------------------------
    # Test 1: Using URL directly (might result in 'SSL off' error if server requires SSL or vice versa)
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
        print("  SKIPPED")

    # ---------------------------------------------------------
    # Test 2: Using Clean URL + connect_args={"ssl": "disable"}
    # This simulates passing dict params to override URL
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
                print(f"  SUCCESS: Connected! (SELECT 1: {result.scalar()})")
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
    # Test 4: Using Components (Constructed URL)
    # ---------------------------------------------------------
    print("\n[Test 4] Constructed URL from components + connect_args={'ssl': 'disable'}")
    # Construct URL manually
    constructed_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    try:
        engine = create_async_engine(
            constructed_url,
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
