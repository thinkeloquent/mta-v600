#!/usr/bin/env python3
"""
PostgreSQL Health Check - Standalone debugging script

Run directly: python postgres_health_check.py

Uses:
- static_config for YAML configuration
- PostgresApiToken for connection config resolution
- asyncpg for native PostgreSQL connection
"""
import asyncio
import json
from pathlib import Path

# ============================================================
# Provider API getter (relative import to avoid circular dependency)
# ============================================================
from ...api_token import PostgresApiToken


async def check_postgres_health(config: dict = None) -> dict:
    print(f"\n{'='*20} Starting PostgreSQL Health Check {'='*20}\n")    
    """
    Check PostgreSQL connectivity using native asyncpg client.

    Args:
        config: Configuration dict (if None, loads from static_config)

    Returns:
        dict: Health check result with success status and data/error
    """
    # Load config if not provided
    if config is None:
        from static_config import config as static_config
        config = static_config

    print("=" * 60)
    print("POSTGRESQL HEALTH CHECK")
    print("=" * 60)

    # Initialize provider from config
    provider = PostgresApiToken(config)
    api_key_result = provider.get_api_key()
    connection_config = provider.get_connection_config()

    # Debug output
    print(f"\n[Config]")
    print(f"  Host: {connection_config.get('host', 'N/A')}")
    print(f"  Port: {connection_config.get('port', 'N/A')}")
    print(f"  Database: {connection_config.get('database', 'N/A')}")
    print(f"  Username: {connection_config.get('username', 'N/A')}")
    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")

    if not api_key_result.has_credentials or api_key_result.is_placeholder:
        print("\n[ERROR] Missing or placeholder credentials")
        return {"success": False, "error": "Missing credentials"}

    # Try to import asyncpg
    try:
        import asyncpg
    except ImportError:
        print("\n[ERROR] asyncpg not installed")
        print("  Install with: pip install asyncpg")
        return {"success": False, "error": "asyncpg not installed"}

    # Build connection parameters from get_connection_config()
    # This includes proper SSL handling for asyncpg
    host = connection_config.get("host", "localhost")
    port = connection_config.get("port", 5432)
    database = connection_config.get("database", "postgres")
    username = connection_config.get("username", "postgres")
    password = connection_config.get("password") or api_key_result.raw_api_key

    # Get SSL config from get_connection_config()
    # asyncpg requires explicit ssl parameter (doesn't parse ?sslmode= from URLs)
    ssl_param = connection_config.get("ssl", False)

    print(f"\n[Connecting]")
    print(f"  postgresql://{username}:****@{host}:{port}/{database}")
    print(f"  SSL: {ssl_param}")

    try:
        # Create connection with explicit ssl parameter
        # asyncpg accepts: False (no SSL), True (SSL with verification),
        # ssl.SSLContext (SSL without verification), or "prefer"
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            timeout=10,
            ssl=ssl_param,
        )

        print(f"\n[Connection Established]")

        # Run health check query
        result = await conn.fetchval("SELECT 1")
        version = await conn.fetchval("SELECT version()")

        print(f"\n[Query Results]")
        print(f"  SELECT 1: {result}")
        print(f"  Version: {version[:60]}..." if len(version) > 60 else f"  Version: {version}")

        # Close connection
        await conn.close()

        return {
            "success": True,
            "message": "Connected to PostgreSQL",
            "data": {
                "host": host,
                "port": port,
                "database": database,
                "version": version,
            },
        }

    except asyncpg.InvalidPasswordError as e:
        print(f"\n[Authentication Error]")
        print(f"  {e}")
        return {
            "success": False,
            "error": "Invalid password",
        }
    except asyncpg.InvalidCatalogNameError as e:
        print(f"\n[Database Error]")
        print(f"  {e}")
        return {
            "success": False,
            "error": f"Database '{database}' does not exist",
        }
    except OSError as e:
        print(f"\n[Connection Error]")
        print(f"  {e}")
        return {
            "success": False,
            "error": f"Cannot connect to {host}:{port}",
        }
    except Exception as e:
        print(f"\n[Exception]")
        print(f"  {type(e).__name__}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    # Load config when run directly as standalone script
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    CONFIG_DIR = PROJECT_ROOT / "common" / "config"

    from static_config import load_yaml_config, config as static_config
    load_yaml_config(config_dir=str(CONFIG_DIR))

    print("\n")
    result = asyncio.run(check_postgres_health(static_config))
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
