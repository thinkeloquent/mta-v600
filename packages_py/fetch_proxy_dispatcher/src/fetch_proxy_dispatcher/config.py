"""
Environment detection and proxy URL mapping.

Reads APP_ENV environment variable to determine the current environment
and maps to appropriate proxy URLs.

Supports user-defined environment names (case-sensitive).
"""
import logging
import os
from typing import Literal, Optional

# Configure logger
logger = logging.getLogger("fetch_proxy_dispatcher.config")

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
    result = raw if raw else default
    logger.debug(f"get_app_env: APP_ENV={raw!r}, default={default!r}, result={result!r}")
    return result


def is_dev() -> bool:
    """Check if current environment is development."""
    env = get_app_env()
    result = env == Environment.DEV
    logger.debug(f"is_dev: env={env!r}, result={result}")
    return result


def get_proxy_url() -> Optional[str]:
    """
    Get the proxy URL for the current environment.

    Reads PROXY_DEV_URL, PROXY_STAGE_URL, PROXY_QA_URL, or PROXY_PROD_URL.
    """
    env = get_app_env()
    env_var = f"PROXY_{env}_URL"
    result = os.environ.get(env_var)
    logger.debug(f"get_proxy_url: env={env!r}, env_var={env_var!r}, result={result!r}")
    return result


def get_agent_proxy_url() -> Optional[str]:
    """
    Get agent proxy URL (HTTP_PROXY or HTTPS_PROXY override).

    HTTPS_PROXY takes precedence over HTTP_PROXY.
    """
    https_proxy = os.environ.get("HTTPS_PROXY")
    http_proxy = os.environ.get("HTTP_PROXY")
    result = https_proxy or http_proxy
    logger.debug(
        f"get_agent_proxy_url: HTTPS_PROXY={https_proxy!r}, HTTP_PROXY={http_proxy!r}, result={result!r}"
    )
    return result


def get_effective_proxy_url() -> Optional[str]:
    """
    Determine the effective proxy URL to use.

    Priority: Agent proxy > Environment-specific proxy
    """
    agent_proxy = get_agent_proxy_url()
    env_proxy = get_proxy_url()
    result = agent_proxy or env_proxy
    logger.debug(
        f"get_effective_proxy_url: agent_proxy={agent_proxy!r}, env_proxy={env_proxy!r}, result={result!r}"
    )
    return result


def is_proxy_configured() -> bool:
    """Check if any proxy is configured."""
    result = get_effective_proxy_url() is not None
    logger.debug(f"is_proxy_configured: result={result}")
    return result
