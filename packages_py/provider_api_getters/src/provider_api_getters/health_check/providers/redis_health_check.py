#!/usr/bin/env python3
"""
Redis Health Check - Standalone debugging script

Run directly: python -m provider_api_getters.health_check.providers.redis_health_check
Or from project root: python packages_py/provider_api_getters/src/provider_api_getters/health_check/providers/redis_health_check.py

Uses:
- static_config for YAML configuration
- RedisApiToken for connection config resolution
- redis-py for native Redis connection
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
    from provider_api_getters.api_token import RedisApiToken
else:
    # Relative import when used as module
    from ...api_token import RedisApiToken


def _mask_url(url: str) -> str:
    """Mask password in Redis URL for safe logging."""
    if not url:
        return "<none>"
    import re
    # Match redis[s]://[user:pass@]host:port/db - mask the password part
    return re.sub(r'(://[^:]*:)[^@]+(@)', r'\1****\2', url)


async def check_redis_health(config: dict = None) -> dict:
    """
    Check Redis connectivity using native redis-py client.

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
    print("REDIS HEALTH CHECK")
    print("=" * 60)

    # Initialize provider from config
    provider = RedisApiToken(config)
    api_key_result = provider.get_api_key()
    connection_url = provider.get_connection_url()

    # Debug output
    print(f"\n[Config]")
    print(f"  Connection URL: {_mask_url(connection_url)}")
    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")

    if not connection_url:
        print("\n[ERROR] No connection URL configured")
        return {"success": False, "error": "No connection URL"}

    # Try to import redis
    try:
        import redis.asyncio as aioredis
    except ImportError:
        print("\n[ERROR] redis not installed")
        print("  Install with: pip install redis")
        return {"success": False, "error": "redis not installed"}

    print(f"\n[Connecting]")
    print(f"  URL: {_mask_url(connection_url)}")

    try:
        # Create async Redis client from URL (handles TLS automatically via rediss://)
        client = aioredis.from_url(
            connection_url,
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
                "connection_url": _mask_url(connection_url),
                "redis_version": info.get("redis_version"),
                "uptime_days": info.get("uptime_in_days"),
            },
        }

    except aioredis.AuthenticationError as e:
        print(f"\n[Authentication Error]")
        print(f"  {e}")
        return {
            "success": False,
            "error": "Authentication failed",
        }
    except aioredis.ConnectionError as e:
        print(f"\n[Connection Error]")
        print(f"  {e}")
        return {
            "success": False,
            "error": f"Cannot connect: {e}",
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
    result = asyncio.run(check_redis_health(static_config))
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
