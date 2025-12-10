#!/usr/bin/env python3
"""
Redis Health Check - Standalone debugging script

Run directly: python redis_health_check.py

Uses:
- static_config for YAML configuration
- RedisApiToken for connection config resolution
- redis-py for native Redis connection
"""
import asyncio
import json
from pathlib import Path

# ============================================================
# Load static config FIRST
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "common" / "config"

from static_config import load_yaml_config, config as static_config
load_yaml_config(config_dir=str(CONFIG_DIR))

# ============================================================
# Provider API getter
# ============================================================
from provider_api_getters import RedisApiToken


async def check_redis_health() -> dict:
    """
    Check Redis connectivity using native redis-py client.

    Returns:
        dict: Health check result with success status and data/error
    """
    print("=" * 60)
    print("REDIS HEALTH CHECK")
    print("=" * 60)

    # Initialize provider from static config
    provider = RedisApiToken(static_config)
    api_key_result = provider.get_api_key()
    connection_config = provider.get_connection_config()

    # Debug output
    print(f"\n[Config]")
    print(f"  Host: {connection_config.get('host', 'N/A')}")
    print(f"  Port: {connection_config.get('port', 'N/A')}")
    print(f"  Database: {connection_config.get('db', 'N/A')}")
    print(f"  Username: {connection_config.get('username', 'N/A')}")
    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")

    # Redis may not require credentials (depending on config)
    # We'll attempt connection regardless

    # Try to import redis
    try:
        import redis.asyncio as redis
    except ImportError:
        print("\n[ERROR] redis not installed")
        print("  Install with: pip install redis")
        return {"success": False, "error": "redis not installed"}

    # Build connection parameters
    host = connection_config.get("host", "localhost")
    port = connection_config.get("port", 6379)
    db = connection_config.get("db", 0)
    username = connection_config.get("username")
    password = api_key_result.api_key if api_key_result.has_credentials else None

    print(f"\n[Connecting]")
    auth_str = f"{username}:****@" if username else ("****@" if password else "")
    print(f"  redis://{auth_str}{host}:{port}/{db}")

    try:
        # Create async Redis client
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            username=username,
            password=password,
            decode_responses=True,
            socket_timeout=10,
        )

        print(f"\n[Connection Established]")

        # Run health check - PING command
        pong = await client.ping()
        info = await client.info("server")

        print(f"\n[Query Results]")
        print(f"  PING: {pong}")
        print(f"  Redis version: {info.get('redis_version', 'N/A')}")
        print(f"  OS: {info.get('os', 'N/A')}")
        print(f"  Uptime (days): {info.get('uptime_in_days', 'N/A')}")

        # Close connection
        await client.aclose()

        return {
            "success": True,
            "message": "Connected to Redis",
            "data": {
                "host": host,
                "port": port,
                "db": db,
                "redis_version": info.get("redis_version"),
                "uptime_days": info.get("uptime_in_days"),
            },
        }

    except redis.AuthenticationError as e:
        print(f"\n[Authentication Error]")
        print(f"  {e}")
        return {
            "success": False,
            "error": "Authentication failed",
        }
    except redis.ConnectionError as e:
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
    print("\n")
    result = asyncio.run(check_redis_health())
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
