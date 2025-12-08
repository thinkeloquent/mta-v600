#!/usr/bin/env python3
"""
PostgreSQL Connection Test (using asyncpg/psycopg)

Authentication: Password
Protocol: PostgreSQL wire protocol (not HTTP)
Health Check: SELECT 1

Note: PostgreSQL uses its own wire protocol, not HTTP.
This file demonstrates both asyncpg and psycopg connections.
"""

import asyncio
import os
from typing import Any

# ============================================================================
# Configuration - Override these values
# ============================================================================

CONFIG = {
    # Required
    "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
    "POSTGRES_PORT": int(os.getenv("POSTGRES_PORT", "5432")),
    "POSTGRES_USER": os.getenv("POSTGRES_USER", "postgres"),
    "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "your_password_here"),
    "POSTGRES_DB": os.getenv("POSTGRES_DB", "postgres"),

    # Optional
    "POSTGRES_SCHEMA": os.getenv("POSTGRES_SCHEMA", "public"),

    # Connection URL (alternative)
    "DATABASE_URL": os.getenv("DATABASE_URL", ""),
}


def get_connection_url() -> str:
    """Get connection URL."""
    if CONFIG["DATABASE_URL"]:
        return CONFIG["DATABASE_URL"]
    return (
        f"postgresql://{CONFIG['POSTGRES_USER']}:{CONFIG['POSTGRES_PASSWORD']}"
        f"@{CONFIG['POSTGRES_HOST']}:{CONFIG['POSTGRES_PORT']}/{CONFIG['POSTGRES_DB']}"
    )


# ============================================================================
# Health Check (using asyncpg)
# ============================================================================

async def health_check_asyncpg() -> dict[str, Any]:
    """Perform health check using asyncpg."""
    print("\n=== PostgreSQL Health Check (asyncpg) ===\n")

    try:
        import asyncpg

        print(f"Connecting to: {CONFIG['POSTGRES_HOST']}:{CONFIG['POSTGRES_PORT']}/{CONFIG['POSTGRES_DB']}")

        conn = await asyncpg.connect(
            host=CONFIG["POSTGRES_HOST"],
            port=CONFIG["POSTGRES_PORT"],
            user=CONFIG["POSTGRES_USER"],
            password=CONFIG["POSTGRES_PASSWORD"],
            database=CONFIG["POSTGRES_DB"],
        )

        # Test connection
        result = await conn.fetchval("SELECT 1")
        print(f"SELECT 1: {result}")

        # Get version
        version = await conn.fetchval("SELECT version()")
        print(f"Version: {version}")

        # Get current database
        db = await conn.fetchval("SELECT current_database()")
        print(f"Database: {db}")

        await conn.close()

        return {"success": True, "data": {"version": version, "database": db}}
    except ImportError:
        print("Error: asyncpg package not installed. Run: pip install asyncpg")
        return {"success": False, "error": "asyncpg package not installed"}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Health Check (using psycopg3)
# ============================================================================

async def health_check_psycopg() -> dict[str, Any]:
    """Perform health check using psycopg3."""
    print("\n=== PostgreSQL Health Check (psycopg3) ===\n")

    try:
        import psycopg

        print(f"Connecting to: {CONFIG['POSTGRES_HOST']}:{CONFIG['POSTGRES_PORT']}/{CONFIG['POSTGRES_DB']}")

        async with await psycopg.AsyncConnection.connect(
            host=CONFIG["POSTGRES_HOST"],
            port=CONFIG["POSTGRES_PORT"],
            user=CONFIG["POSTGRES_USER"],
            password=CONFIG["POSTGRES_PASSWORD"],
            dbname=CONFIG["POSTGRES_DB"],
        ) as conn:
            async with conn.cursor() as cur:
                # Test connection
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                print(f"SELECT 1: {result[0]}")

                # Get version
                await cur.execute("SELECT version()")
                version = (await cur.fetchone())[0]
                print(f"Version: {version}")

                # Get current database
                await cur.execute("SELECT current_database()")
                db = (await cur.fetchone())[0]
                print(f"Database: {db}")

        return {"success": True, "data": {"version": version, "database": db}}
    except ImportError:
        print("Error: psycopg package not installed. Run: pip install psycopg[binary]")
        return {"success": False, "error": "psycopg package not installed"}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Sample Operations
# ============================================================================

async def sample_operations() -> dict[str, Any]:
    """Perform sample PostgreSQL operations."""
    print("\n=== Sample PostgreSQL Operations ===\n")

    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=CONFIG["POSTGRES_HOST"],
            port=CONFIG["POSTGRES_PORT"],
            user=CONFIG["POSTGRES_USER"],
            password=CONFIG["POSTGRES_PASSWORD"],
            database=CONFIG["POSTGRES_DB"],
        )

        # List schemas
        schemas = await conn.fetch("""
            SELECT schema_name
            FROM information_schema.schemata
            ORDER BY schema_name
        """)
        print("Schemas:")
        for schema in schemas[:10]:
            print(f"  - {schema['schema_name']}")

        # List tables in public schema
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name
        """, CONFIG["POSTGRES_SCHEMA"])
        print(f"\nTables in {CONFIG['POSTGRES_SCHEMA']}:")
        for table in tables[:10]:
            print(f"  - {table['table_name']}")

        # Get database size
        size = await conn.fetchval("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)
        print(f"\nDatabase size: {size}")

        await conn.close()

        return {"success": True}
    except ImportError:
        print("Error: asyncpg package not installed. Run: pip install asyncpg")
        return {"success": False, "error": "asyncpg package not installed"}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# HTTP-based PostgreSQL (PostgREST example)
# ============================================================================

async def health_check_postgrest() -> dict[str, Any]:
    """Health check for PostgREST API."""
    print("\n=== PostgREST API Health Check ===\n")

    import httpx

    postgrest_url = os.getenv("POSTGREST_URL", "")
    postgrest_token = os.getenv("POSTGREST_TOKEN", "")

    if not postgrest_url:
        print("PostgREST URL not configured. Set POSTGREST_URL environment variable")
        return {"success": False, "error": "PostgREST URL not configured"}

    async with httpx.AsyncClient() as client:
        try:
            headers = {"Accept": "application/json"}
            if postgrest_token:
                headers["Authorization"] = f"Bearer {postgrest_token}"

            response = await client.get(
                f"{postgrest_url}/",
                headers=headers,
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("PostgREST is accessible")
            else:
                print(f"Response: {response.text}")

            return {"success": response.status_code == 200}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("PostgreSQL Connection Test")
    print("==========================")
    print(f"Host: {CONFIG['POSTGRES_HOST']}:{CONFIG['POSTGRES_PORT']}")
    print(f"Database: {CONFIG['POSTGRES_DB']}")
    print(f"User: {CONFIG['POSTGRES_USER']}")

    await health_check_asyncpg()
    # await health_check_psycopg()  # Alternative using psycopg3
    # await sample_operations()
    # await health_check_postgrest()  # For PostgREST HTTP API


if __name__ == "__main__":
    asyncio.run(main())
