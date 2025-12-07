"""
Configuration utilities for connection-pool
"""

import time
import uuid
from dataclasses import replace
from typing import Tuple

from .types import ConnectionPoolConfig


# Default connection pool configuration
DEFAULT_CONNECTION_POOL_CONFIG = ConnectionPoolConfig(
    id="default-pool",
    max_connections=100,
    max_connections_per_host=10,
    max_idle_connections=20,
    idle_timeout_seconds=60.0,
    keep_alive_timeout_seconds=30.0,
    connect_timeout_seconds=10.0,
    enable_health_check=True,
    health_check_interval_seconds=30.0,
    max_connection_age_seconds=300.0,
    keep_alive=True,
    queue_requests=True,
    max_queue_size=1000,
    queue_timeout_seconds=30.0,
)


def merge_config(user_config: ConnectionPoolConfig) -> ConnectionPoolConfig:
    """Merge user config with defaults (user config takes precedence)"""
    return user_config


def validate_config(config: ConnectionPoolConfig) -> list[str]:
    """Validate configuration values"""
    errors = []

    if config.max_connections < 1:
        errors.append("max_connections must be at least 1")

    if config.max_connections_per_host < 1:
        errors.append("max_connections_per_host must be at least 1")

    if config.max_idle_connections < 0:
        errors.append("max_idle_connections must be non-negative")

    if config.idle_timeout_seconds < 0:
        errors.append("idle_timeout_seconds must be non-negative")

    if config.keep_alive_timeout_seconds < 0:
        errors.append("keep_alive_timeout_seconds must be non-negative")

    if config.connect_timeout_seconds < 0:
        errors.append("connect_timeout_seconds must be non-negative")

    if config.health_check_interval_seconds < 1.0:
        errors.append("health_check_interval_seconds must be at least 1.0")

    if config.max_connection_age_seconds < 0:
        errors.append("max_connection_age_seconds must be non-negative")

    if config.max_queue_size < 0:
        errors.append("max_queue_size must be non-negative")

    if config.queue_timeout_seconds < 0:
        errors.append("queue_timeout_seconds must be non-negative")

    # Cross-field validations
    if config.max_connections_per_host > config.max_connections:
        errors.append("max_connections_per_host cannot exceed max_connections")

    if config.max_idle_connections > config.max_connections:
        errors.append("max_idle_connections cannot exceed max_connections")

    return errors


def get_host_key(host: str, port: int) -> str:
    """Generate a host key from host and port"""
    return f"{host}:{port}"


def parse_host_key(host_key: str) -> Tuple[str, int]:
    """Parse a host key back to host and port"""
    last_colon = host_key.rfind(":")
    if last_colon == -1:
        raise ValueError(f"Invalid host key: {host_key}")
    return host_key[:last_colon], int(host_key[last_colon + 1 :])


def generate_connection_id() -> str:
    """Generate a unique connection ID"""
    return f"conn-{int(time.time() * 1000)}-{uuid.uuid4().hex[:9]}"
