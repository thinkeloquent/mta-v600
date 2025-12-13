import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

# Load env from parent directories if needed, or specific .env
load_dotenv()

async def main():
    print("="*60)
    print("asyncpg Connection Test")
    print("="*60)

    # 1. Gather config
    db_url = os.getenv("DATABASE_URL")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    print(f"Config:")
    print(f"  DATABASE_URL: {db_url}")
    print(f"  Host: {host}:{port}")
    print(f"  User: {user}")
    print(f"  DB:   {dbname}")
    
    # ---------------------------------------------------------
    # Test 1: Using DATABASE_URL + ssl="disable" (String)
    # ---------------------------------------------------------
    print("\n[Test 1] Using DATABASE_URL + ssl='disable' (explicit kwarg)")
    if db_url:
        try:
            # Note: asyncpg requires 'ssl' kwarg to disable SSL explicitly if server doesn't support it 
            # or if we want to ignore URL params.
            conn = await asyncpg.connect(db_url, ssl="disable")
            print("  SUCCESS: Connected!")
            version = await conn.fetchval("SELECT version()")
            print(f"  Version: {version}")
            await conn.close()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED: DATABASE_URL not set")

    # ---------------------------------------------------------
    # Test 2: Using DATABASE_URL + ssl=False (Boolean)
    # ---------------------------------------------------------
    print("\n[Test 2] Using DATABASE_URL + ssl=False (explicit kwarg)")
    if db_url:
        try:
            conn = await asyncpg.connect(db_url, ssl=False)
            print("  SUCCESS: Connected!")
            await conn.close()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED")

    # ---------------------------------------------------------
    # Test 3: Using Components + ssl="disable"
    # ---------------------------------------------------------
    print("\n[Test 3] Using Components (host, user...) + ssl='disable'")
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            ssl="disable"
        )
        print("  SUCCESS: Connected!")
        await conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

    # ---------------------------------------------------------
    # Test 4: Using Components + ssl=False
    # ---------------------------------------------------------
    print("\n[Test 4] Using Components + ssl=False")
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            ssl=False
        )
        print("  SUCCESS: Connected!")
        await conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
