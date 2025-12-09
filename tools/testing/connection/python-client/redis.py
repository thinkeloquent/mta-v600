#!/usr/bin/env python3
"""
Redis Connection Test - Python Client Integration

Authentication: Password or ACL (username:password)
Protocol: Redis protocol (not HTTP)
Health Check: PING command

Uses internal packages:
  - provider_api_getters: Credential resolution
  - app_static_config_yaml: YAML configuration loading

Note: Redis uses its own protocol, not HTTP. This file uses redis-py library.
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
from provider_api_getters import RedisApiToken, ProviderHealthChecker

# ============================================================================
# Configuration - Exposed for debugging
# ============================================================================
provider = RedisApiToken(static_config)
api_key_result = provider.get_api_key()

CONFIG = {
    # From provider_api_getters or environment
    "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
    "REDIS_PORT": int(os.getenv("REDIS_PORT", "6379")),
    "REDIS_PASSWORD": api_key_result.api_key or os.getenv("REDIS_PASSWORD", ""),
    "REDIS_USERNAME": api_key_result.username or os.getenv("REDIS_USERNAME", ""),
    "REDIS_DB": int(os.getenv("REDIS_DB", "0")),

    # Optional: TLS Configuration
    "REDIS_USE_SSL": os.getenv("REDIS_USE_SSL", "false").lower() == "true",

    # Debug
    "DEBUG": os.getenv("DEBUG", "true").lower() not in ("false", "0"),
}


# ============================================================================
# Health Check
# ============================================================================
async def health_check() -> dict[str, Any]:
    """Health check using ProviderHealthChecker."""
    print("\n=== Redis Health Check (ProviderHealthChecker) ===\n")

    checker = ProviderHealthChecker(static_config)
    result = await checker.check("redis")

    print(f"Status: {result.status}")
    if result.latency_ms:
        print(f"Latency: {result.latency_ms:.2f}ms")
    if result.message:
        print(f"Message: {result.message}")
    if result.error:
        print(f"Error: {result.error}")

    return {"success": result.status == "connected", "result": result}


# ============================================================================
# Sample Operations using redis-py
# ============================================================================
async def health_check_redis_py() -> dict[str, Any]:
    """Perform health check using redis-py async."""
    print("\n=== Redis Health Check (redis-py) ===\n")

    try:
        import redis.asyncio as redis

        # Build connection URL
        auth = ""
        if CONFIG["REDIS_USERNAME"] and CONFIG["REDIS_PASSWORD"]:
            auth = f"{CONFIG['REDIS_USERNAME']}:{CONFIG['REDIS_PASSWORD']}@"
        elif CONFIG["REDIS_PASSWORD"]:
            auth = f":{CONFIG['REDIS_PASSWORD']}@"

        protocol = "rediss" if CONFIG["REDIS_USE_SSL"] else "redis"
        url = f"{protocol}://{auth}{CONFIG['REDIS_HOST']}:{CONFIG['REDIS_PORT']}/{CONFIG['REDIS_DB']}"

        print(f"Connecting to: {protocol}://{CONFIG['REDIS_HOST']}:{CONFIG['REDIS_PORT']}/{CONFIG['REDIS_DB']}")

        client = redis.from_url(url)

        # Test connection
        pong = await client.ping()
        print(f"PING: {pong}")

        # Get server info
        info = await client.info("server")
        print(f"Redis Version: {info.get('redis_version')}")
        print(f"OS: {info.get('os')}")

        await client.close()

        return {"success": True, "data": {"ping": pong, "version": info.get("redis_version")}}
    except ImportError:
        print("Error: redis package not installed. Run: pip install redis")
        return {"success": False, "error": "redis package not installed"}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


async def sample_operations() -> dict[str, Any]:
    """Perform sample Redis operations."""
    print("\n=== Sample Redis Operations ===\n")

    try:
        import redis.asyncio as redis

        # Build connection URL
        auth = ""
        if CONFIG["REDIS_USERNAME"] and CONFIG["REDIS_PASSWORD"]:
            auth = f"{CONFIG['REDIS_USERNAME']}:{CONFIG['REDIS_PASSWORD']}@"
        elif CONFIG["REDIS_PASSWORD"]:
            auth = f":{CONFIG['REDIS_PASSWORD']}@"

        protocol = "rediss" if CONFIG["REDIS_USE_SSL"] else "redis"
        url = f"{protocol}://{auth}{CONFIG['REDIS_HOST']}:{CONFIG['REDIS_PORT']}/{CONFIG['REDIS_DB']}"

        client = redis.from_url(url)

        # SET/GET
        await client.set("test:key", "hello world")
        value = await client.get("test:key")
        print(f"SET/GET: {value}")

        # HSET/HGET
        await client.hset("test:hash", mapping={"field1": "value1", "field2": "value2"})
        hash_value = await client.hgetall("test:hash")
        print(f"HSET/HGETALL: {hash_value}")

        # LIST
        await client.rpush("test:list", "item1", "item2", "item3")
        list_value = await client.lrange("test:list", 0, -1)
        print(f"RPUSH/LRANGE: {list_value}")

        # Cleanup
        await client.delete("test:key", "test:hash", "test:list")
        print("Cleanup: Deleted test keys")

        await client.close()

        return {"success": True}
    except ImportError:
        print("Error: redis package not installed. Run: pip install redis")
        return {"success": False, "error": "redis package not installed"}
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================
async def main():
    """Run connection tests."""
    print("Redis Connection Test (Python Client Integration)")
    print("=" * 49)
    print(f"Host: {CONFIG['REDIS_HOST']}:{CONFIG['REDIS_PORT']}")
    print(f"Database: {CONFIG['REDIS_DB']}")
    print(f"SSL: {CONFIG['REDIS_USE_SSL']}")
    print(f"Debug: {CONFIG['DEBUG']}")

    await health_check()

    # Uncomment to run additional tests:
    # await health_check_redis_py()
    # await sample_operations()


if __name__ == "__main__":
    asyncio.run(main())
