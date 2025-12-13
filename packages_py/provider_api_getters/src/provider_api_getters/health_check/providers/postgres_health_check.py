#!/usr/bin/env python3
"""
PostgreSQL Health Check - Standalone debugging script

Run directly: python -m provider_api_getters.health_check.providers.postgres_health_check
Or from project root: python packages_py/provider_api_getters/src/provider_api_getters/health_check/providers/postgres_health_check.py

Uses:
- static_config for YAML configuration
- PostgresApiToken for connection config resolution
- db_connection_postgres for connection management
"""
import asyncio
import json
import sys
from pathlib import Path

# ============================================================
# Handle both direct execution and module import
# ============================================================
if __name__ == "__main__":
    # Add src directory to path for direct execution
    _src_dir = Path(__file__).parent.parent.parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from provider_api_getters.api_token import PostgresApiToken
else:
    # Relative import when used as module
    from ...api_token import PostgresApiToken

try:
    from db_connection_postgres import (
        DatabaseConfig,
        init_db,
        close_db,
        get_health_status,
    )
except ImportError:
    print("[ERROR] db_connection_postgres package not found.")
    print("Ensure packages_py/db_connection_postgres is installed.")
    sys.exit(1)


async def check_postgres_health(config: dict = None) -> dict:
    """
    Check PostgreSQL connectivity using db_connection_postgres package.

    Args:
        config: Configuration dict (if None, loads from static_config)

    Returns:
        dict: Health check result with success status and data/error
    """
    print(f"\n{'='*20} Starting PostgreSQL Health Check {'='*20}\n")
    
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
    connection_host = connection_config.get('host', 'N/A')
    connection_port = connection_config.get('port', 'N/A')
    connection_db = connection_config.get('database', 'N/A')
    connection_user = connection_config.get('username', 'N/A')

    print(f"\n[Config]")
    print(f"  Host: {connection_host}")
    print(f"  Port: {connection_port}")
    print(f"  Database: {connection_db}")
    print(f"  Username: {connection_user}")
    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")

    if not api_key_result.has_credentials or api_key_result.is_placeholder:
        print("\n[ERROR] Missing or placeholder credentials")
        return {"success": False, "error": "Missing credentials"}

    # Map connection_config to DatabaseConfig
    host = connection_config.get("host", "localhost")
    port = int(connection_config.get("port", 5432))
    database = connection_config.get("database", "postgres")
    username = connection_config.get("username", "postgres")
    password = connection_config.get("password") or api_key_result.raw_api_key
    
    # Handle SSL mapping
    # connection_config['ssl'] might be bool or string
    raw_ssl = connection_config.get("ssl", False)
    ssl_mode = "disable"
    if isinstance(raw_ssl, str):
        ssl_mode = raw_ssl
    elif raw_ssl is True:
        ssl_mode = "require" # Default to require if explicitly True
    
    print(f"\n[Connecting via db_connection_postgres]")
    print(f"  SSL Mode: {ssl_mode}")

    db_config = DatabaseConfig(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password,
        ssl_mode=ssl_mode,
        echo=True # Enable echo for debug script
    )

    try:
        # Initialize the global DB manager with our config
        await init_db(db_config)
        
        # Run health check
        health = await get_health_status()
        
        # Must close connections
        await close_db()

        if health.get("status") == "healthy":
            pg_version = health.get('pg_version')
            print(f"\n[Connection Established]")
            print(f"  Version: {pg_version}")
            
            return {
                "success": True,
                "message": "Connected to PostgreSQL",
                "data": {
                    "host": host,
                    "port": port,
                    "database": database,
                    "version": pg_version,
                },
            }
        else:
            error_msg = health.get('error', 'Unknown error')
            print(f"\n[Connection Failed]")
            print(f"  Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
            }

    except Exception as e:
        print(f"\n[Exception]")
        print(f"  {type(e).__name__}: {e}")
        # Ensure fallback close
        try:
            await close_db()
        except:
            pass
            
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
