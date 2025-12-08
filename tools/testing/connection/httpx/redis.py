#!/usr/bin/env python3
"""
Redis Connection Test (using redis-py)

Authentication: Password or ACL (username:password)
Protocol: Redis protocol (not HTTP)
Health Check: PING command

Note: Redis uses its own protocol, not HTTP. This file uses redis-py library.
For HTTP-based Redis (Redis REST API), see the httpx examples.
"""

import asyncio
import os
from typing import Any

# ============================================================================
# Configuration - Override these values
# ============================================================================

CONFIG = {
    # Required
    "REDIS_HOST": os.getenv("REDIS_HOST", "localhost"),
    "REDIS_PORT": int(os.getenv("REDIS_PORT", "6379")),
    "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD", ""),
    "REDIS_USERNAME": os.getenv("REDIS_USERNAME", ""),  # For ACL (Redis 6+)
    "REDIS_DB": int(os.getenv("REDIS_DB", "0")),

    # Optional: TLS Configuration
    "REDIS_USE_SSL": os.getenv("REDIS_USE_SSL", "false").lower() == "true",
}


# ============================================================================
# Health Check (using redis-py)
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


# ============================================================================
# Sample Operations
# ============================================================================

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
# HTTP-based Redis (Upstash REST API example)
# ============================================================================

async def health_check_upstash() -> dict[str, Any]:
    """Health check for Upstash Redis REST API."""
    print("\n=== Upstash Redis REST API Health Check ===\n")

    import httpx

    upstash_url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

    if not upstash_url or not upstash_token:
        print("Upstash credentials not configured. Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN")
        return {"success": False, "error": "Upstash credentials not configured"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{upstash_url}/ping",
                headers={
                    "Authorization": f"Bearer {upstash_token}",
                },
            )

            data = response.json()
            print(f"Status: {response.status_code}")
            print(f"Response: {data}")

            return {"success": response.status_code == 200, "data": data}
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Run Tests
# ============================================================================

async def main():
    """Run connection tests."""
    print("Redis Connection Test")
    print("=====================")
    print(f"Host: {CONFIG['REDIS_HOST']}:{CONFIG['REDIS_PORT']}")
    print(f"Database: {CONFIG['REDIS_DB']}")
    print(f"SSL: {CONFIG['REDIS_USE_SSL']}")

    await health_check_redis_py()
    # await sample_operations()
    # await health_check_upstash()  # For Upstash REST API


if __name__ == "__main__":
    asyncio.run(main())
