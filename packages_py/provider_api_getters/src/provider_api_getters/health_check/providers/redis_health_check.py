#!/usr/bin/env python3
"""
Redis Health Check - Standalone debugging script with explicit 7-step pattern.

Flow: YamlConfig -> ProviderConfig -> ConnectionConfig -> ClientConfig -> Connect -> Query -> Response

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
import time
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


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"Step: {title}")
    print("=" * 60)


def print_json(data: dict) -> None:
    """Print JSON data with indentation."""
    print(json.dumps(data, indent=2, default=str))


def mask_sensitive(value: str, show_chars: int = 4) -> str:
    """Mask sensitive values for logging."""
    if not value:
        return "<none>"
    if len(value) <= show_chars:
        return "*" * len(value)
    return value[:show_chars] + "***"


async def check_redis_health(config: dict = None) -> dict:
    """
    Redis Health Check - Explicit 7-step building block pattern.

    Flow: YamlConfig -> ProviderConfig -> ConnectionConfig -> ClientConfig -> Connect -> Query -> Response

    This pattern is identical across:
    - FastAPI endpoints
    - Fastify endpoints
    - Standalone scripts (this file)
    - CLI tools
    - SDKs

    Args:
        config: Configuration store (if None, uses staticConfig)

    Returns:
        dict: Health check result with success status, data/error, and configUsed metadata
    """
    # ============================================================
    # Step 1: YAML CONFIG LOADING
    # ============================================================
    print_section("1. YAML CONFIG LOADING")

    if config is None:
        from static_config import config as static_config
        config = static_config

    config_source = config.get("_source", "unknown")
    print(f"  Loaded from: {config_source}")

    # ============================================================
    # Step 2: PROVIDER CONFIG EXTRACTION
    # ============================================================
    print_section("2. PROVIDER CONFIG EXTRACTION")

    provider = RedisApiToken(config)

    provider_config = {
        "provider_name": provider.provider_name,
    }
    print_json(provider_config)

    # ============================================================
    # Step 3: CONNECTION CONFIG RESOLUTION
    # ============================================================
    print_section("3. CONNECTION CONFIG RESOLUTION")

    connection_config = provider.get_connection_config()
    api_key_result = provider.get_api_key()

    conn_config = {
        "host": connection_config.get("host", "localhost"),
        "port": connection_config.get("port", 6379),
        "database": connection_config.get("database", 0),
        "username": connection_config.get("username"),
        "has_password": bool(api_key_result.api_key),
    }
    print_json(conn_config)

    print(f"  Has credentials: {api_key_result.has_credentials}")
    print(f"  Is placeholder: {api_key_result.is_placeholder}")

    if not api_key_result.has_credentials or api_key_result.is_placeholder:
        return {
            "success": False,
            "error": "Missing or placeholder credentials",
            "config_used": {
                "provider": provider_config,
                "connection": conn_config,
            },
        }

    # ============================================================
    # Step 4: CLIENT CONFIG (redis-py options)
    # ============================================================
    print_section("4. CLIENT CONFIG")

    # Try to import redis
    try:
        import redis.asyncio as aioredis
    except ImportError:
        print("  ERROR: redis not installed")
        print("  Install with: pip install redis")
        return {
            "success": False,
            "error": "redis not installed",
            "config_used": {
                "provider": provider_config,
                "connection": conn_config,
            },
        }

    # Build redis-py client options
    # IMPORTANT: No retries - fail fast on first attempt
    # Use Retry with retries=0 to completely disable retry behavior
    from redis.backoff import NoBackoff
    from redis.retry import Retry
    no_retry = Retry(NoBackoff(), retries=0)

    client_config = {
        "host": conn_config["host"],
        "port": conn_config["port"],
        "db": conn_config["database"],
        "username": conn_config["username"],
        "password": api_key_result.api_key,
        "socket_timeout": 10,           # 10 second socket timeout
        "socket_connect_timeout": 10,   # 10 second connection timeout
        "retry_on_timeout": False,      # Don't retry on timeout
        "retry_on_error": [],           # Don't retry on any errors
        "retry": no_retry,              # Disable all retry logic
        "decode_responses": True,
    }

    print(f"  Host: {client_config['host']}")
    print(f"  Port: {client_config['port']}")
    print(f"  Database: {client_config['db']}")
    print(f"  Username: {client_config['username'] or 'N/A'}")
    print(f"  Password: {mask_sensitive(client_config['password'])}")
    print(f"  Socket timeout: {client_config['socket_timeout']}s")
    print(f"  Connect timeout: {client_config['socket_connect_timeout']}s")
    print(f"  Retries: disabled (fail fast)")

    # ============================================================
    # Step 5: CONNECT
    # ============================================================
    print_section("5. CONNECT")

    connection_url = f"redis://{conn_config['username'] + ':****@' if conn_config['username'] else ''}{conn_config['host']}:{conn_config['port']}/{conn_config['database']}"
    print(f"  URL: {connection_url}")

    client = aioredis.Redis(**client_config)

    start_time = time.perf_counter()

    try:
        print("  Connecting...")
        # Test connection with PING
        await client.ping()
        print("  Connected!")

        # ============================================================
        # Step 6: QUERY (PING and INFO)
        # ============================================================
        print_section("6. QUERY")

        print("  Sending PING...")
        pong = await client.ping()
        print(f"  PING response: {pong}")

        print("  Getting server info...")
        info = await client.info("server")
        version = info.get("redis_version", "unknown")
        print(f"  Redis version: {version}")

        latency_ms = (time.perf_counter() - start_time) * 1000

        # ============================================================
        # Step 7: RESPONSE HANDLING
        # ============================================================
        print_section("7. RESPONSE HANDLING")

        print(f"  Status: connected")
        print(f"  Latency: {latency_ms:.2f}ms")

        # Build config_used for debugging
        config_used = {
            "provider": provider_config,
            "connection": conn_config,
            "client_options": {
                "socket_timeout": client_config["socket_timeout"],
                "socket_connect_timeout": client_config["socket_connect_timeout"],
                "retries": "disabled",
            },
        }

        return {
            "success": True,
            "message": "Connected to Redis",
            "data": {
                "host": conn_config["host"],
                "port": conn_config["port"],
                "database": conn_config["database"],
                "version": version,
                "pong": pong,
            },
            "latency_ms": latency_ms,
            "config_used": config_used,
        }

    except aioredis.AuthenticationError as e:
        latency_ms = (time.perf_counter() - start_time) * 1000

        # ============================================================
        # Step 7: RESPONSE HANDLING (Error)
        # ============================================================
        print_section("7. RESPONSE HANDLING (Error)")

        print(f"  Error: {e}")
        print(f"  Latency: {latency_ms:.2f}ms")
        print("  [Authentication Error]")

        config_used = {
            "provider": provider_config,
            "connection": conn_config,
            "client_options": {
                "socket_timeout": client_config["socket_timeout"],
                "socket_connect_timeout": client_config["socket_connect_timeout"],
                "retries": "disabled",
            },
        }

        return {
            "success": False,
            "error": "Invalid password",
            "latency_ms": latency_ms,
            "config_used": config_used,
        }

    except aioredis.ConnectionError as e:
        latency_ms = (time.perf_counter() - start_time) * 1000

        # ============================================================
        # Step 7: RESPONSE HANDLING (Error)
        # ============================================================
        print_section("7. RESPONSE HANDLING (Error)")

        print(f"  Error: {e}")
        print(f"  Latency: {latency_ms:.2f}ms")
        print("  [Connection Error]")

        config_used = {
            "provider": provider_config,
            "connection": conn_config,
            "client_options": {
                "socket_timeout": client_config["socket_timeout"],
                "socket_connect_timeout": client_config["socket_connect_timeout"],
                "retries": "disabled",
            },
        }

        return {
            "success": False,
            "error": f"Cannot connect to {conn_config['host']}:{conn_config['port']}",
            "latency_ms": latency_ms,
            "config_used": config_used,
        }

    except aioredis.TimeoutError as e:
        latency_ms = (time.perf_counter() - start_time) * 1000

        # ============================================================
        # Step 7: RESPONSE HANDLING (Error)
        # ============================================================
        print_section("7. RESPONSE HANDLING (Error)")

        print(f"  Error: {e}")
        print(f"  Latency: {latency_ms:.2f}ms")
        print("  [Timeout Error]")

        config_used = {
            "provider": provider_config,
            "connection": conn_config,
            "client_options": {
                "socket_timeout": client_config["socket_timeout"],
                "socket_connect_timeout": client_config["socket_connect_timeout"],
                "retries": "disabled",
            },
        }

        return {
            "success": False,
            "error": f"Connection timed out after {client_config['socket_connect_timeout']}s",
            "latency_ms": latency_ms,
            "config_used": config_used,
        }

    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000

        # ============================================================
        # Step 7: RESPONSE HANDLING (Error)
        # ============================================================
        print_section("7. RESPONSE HANDLING (Error)")

        print(f"  Error: {e}")
        print(f"  Latency: {latency_ms:.2f}ms")
        print(f"  [Exception: {type(e).__name__}]")

        config_used = {
            "provider": provider_config,
            "connection": conn_config,
            "client_options": {
                "socket_timeout": client_config["socket_timeout"],
                "socket_connect_timeout": client_config["socket_connect_timeout"],
                "retries": "disabled",
            },
        }

        return {
            "success": False,
            "error": str(e),
            "latency_ms": latency_ms,
            "config_used": config_used,
        }

    finally:
        await client.aclose()


if __name__ == "__main__":
    # Load config when run directly as standalone script
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    CONFIG_DIR = PROJECT_ROOT / "common" / "config"

    from static_config import load_yaml_config, config as static_config
    load_yaml_config(config_dir=str(CONFIG_DIR))

    print("\n")
    print("=" * 60)
    print("REDIS HEALTH CHECK - Explicit 7-Step Pattern")
    print("=" * 60)
    print("Flow: YamlConfig -> Provider -> Connection -> Client -> Connect -> Query -> Response")

    result = asyncio.run(check_redis_health(static_config))

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
