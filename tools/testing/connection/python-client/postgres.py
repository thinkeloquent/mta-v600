#!/usr/bin/env python3
"""
PostgreSQL Connection Test - Python Client Integration

Authentication: Password
Protocol: PostgreSQL wire protocol (not HTTP)
Health Check: SELECT 1

Uses internal packages:
  - provider_api_getters: Credential resolution
  - app_static_config_yaml: YAML configuration loading

Note: PostgreSQL uses its own wire protocol, not HTTP.
This file uses asyncpg for async PostgreSQL connections.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# ============================================================================
# Project Setup - Add packages to path
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "app_static_config_yaml" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "provider_api_getters" / "src"))

# Load static config
from static_config import load_yaml_config, config as static_config
CONFIG_DIR = PROJECT_ROOT / "common" / "config"
load_yaml_config(config_dir=str(CONFIG_DIR))

# Import internal packages
from provider_api_getters import PostgresApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = PostgresApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters or environment
    "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
    "POSTGRES_PORT": int(os.getenv("POSTGRES_PORT", "5432")),
    "POSTGRES_USER": api_key_result.username or os.getenv("POSTGRES_USER", "postgres"),
    "POSTGRES_PASSWORD": api_key_result.api_key or os.getenv("POSTGRES_PASSWORD", ""),
    "POSTGRES_DB": os.getenv("POSTGRES_DB", "postgres"),
    "POSTGRES_SCHEMA": os.getenv("POSTGRES_SCHEMA", "public"),

    # Connection URL (alternative)
    "DATABASE_URL": os.getenv("DATABASE_URL", ""),

    # Debug
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
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
# Health Check
# ============================================================================
async def health_check() -> dict[str, Any]:
    """Health check using ProviderHealthChecker."""
    print("\n=== PostgreSQL Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("postgres")

    print(f"Status: {result.status}")
    if result.latency_ms:
        print(f"Latency: {result.latency_ms:.2f}ms")
    if result.message:
        print(f"Message: {result.message}")
    if result.error:
        print(f"Error: {result.error}")

    return {"success": result.status == "connected", "result": result}


# ============================================================================
# Sample Operations using asyncpg
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
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("PostgreSQL Connection Test (Python Client Integration)")
    print("=" * 55)
    print(f"Host: {CONFIG['POSTGRES_HOST']}:{CONFIG['POSTGRES_PORT']}")
    print(f"Database: {CONFIG['POSTGRES_DB']}")
    print(f"User: {CONFIG['POSTGRES_USER']}")
    print(f"Schema: {CONFIG['POSTGRES_SCHEMA']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await health_check_asyncpg()
    # await sample_operations()


if __name__ == "__main__":
    asyncio.run(main())
