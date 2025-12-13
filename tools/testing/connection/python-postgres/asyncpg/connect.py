import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def get_db_url():
    """Always build from components to avoid broken DATABASE_URL env var."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")
    
    if not host: host = "localhost"
    
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

async def main():
    print("="*60)
    print("asyncpg Connection Test (Enhanced)")
    print("="*60)

    db_url = get_db_url()
    
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    print(f"Config:")
    print(f"  Target URL: {db_url}")
    print(f"  Components: {host}:{port}")

    # ---------------------------------------------------------
    # Test 3/4: Components (Already passing, but good to keep)
    # ---------------------------------------------------------
    print("\n[Test] Components + ssl='disable'")
    try:
        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password, database=dbname,
            ssl="disable"
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
