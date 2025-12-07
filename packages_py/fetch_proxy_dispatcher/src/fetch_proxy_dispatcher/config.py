"""
Environment detection and proxy URL mapping.

Reads APP_ENV environment variable to determine the current environment
and maps to appropriate proxy URLs.

Supports user-defined environment names (case-sensitive).
"""
import os
from typing import Literal, Optional

# Legacy type alias for backward compatibility
AppEnv = Literal["DEV", "STAGE", "QA", "PROD"]


class Environment:
    """Environment constants (legacy)."""
    DEV: Literal["DEV"] = "DEV"
    STAGE: Literal["STAGE"] = "STAGE"
    QA: Literal["QA"] = "QA"
    PROD: Literal["PROD"] = "PROD"


def get_app_env(default: str = "DEV") -> str:
    """
    Get the current application environment from APP_ENV.

    Returns the raw value (case-sensitive) or default if not set.
    Accepts any user-defined environment name.

    Args:
        default: Default environment if APP_ENV is not set.

    Returns:
        Environment string from APP_ENV, or default.
    """
    raw = os.environ.get("APP_ENV", "")
    return raw if raw else default


def is_dev() -> bool:
    """Check if current environment is development."""
    return get_app_env() == Environment.DEV


def get_proxy_url() -> Optional[str]:
    """
    Get the proxy URL for the current environment.

    Reads PROXY_DEV_URL, PROXY_STAGE_URL, PROXY_QA_URL, or PROXY_PROD_URL.
    """
    env = get_app_env()
    return os.environ.get(f"PROXY_{env}_URL")


def get_agent_proxy_url() -> Optional[str]:
    """
    Get agent proxy URL (HTTP_PROXY or HTTPS_PROXY override).

    HTTPS_PROXY takes precedence over HTTP_PROXY.
    """
    return os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


def get_effective_proxy_url() -> Optional[str]:
    """
    Determine the effective proxy URL to use.

    Priority: Agent proxy > Environment-specific proxy
    """
    return get_agent_proxy_url() or get_proxy_url()


def is_proxy_configured() -> bool:
    """Check if any proxy is configured."""
    return get_effective_proxy_url() is not None
