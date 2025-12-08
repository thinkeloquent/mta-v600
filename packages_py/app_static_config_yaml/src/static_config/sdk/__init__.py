"""SDK utilities for static configuration management.

Provides high-level functions for loading configuration with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional

from ..config_store import config, LoadResult


def get_config_path() -> Path:
    """
    Get the default configuration path.

    The path is resolved relative to the common/config directory in the monorepo.
    """
    # Try to find common/config relative to this package
    # Go up from: packages_py/app_static_config_yaml/src/static_config/sdk
    # To: common/config
    current = Path(__file__).resolve()
    for _ in range(6):  # Go up 6 levels to reach monorepo root
        current = current.parent
    return current / "common" / "config"


def load_yaml_config(
    config_dir: Optional[str] = None,
    app_env: Optional[str] = None,
) -> LoadResult:
    """
    Load YAML configuration with sensible defaults.

    This function should be called AFTER vault secrets are loaded,
    so that APP_ENV can be set from vault.

    Args:
        config_dir: Path to config directory (default: common/config)
        app_env: Environment name (default: from APP_ENV env var or 'dev')

    Returns:
        LoadResult with load status information
    """
    # Use provided config_dir or default to common/config
    path = config_dir or str(get_config_path())

    # Get APP_ENV from environment if not provided, convert to lowercase for consistent file matching
    raw_env = app_env or os.environ.get("APP_ENV", "dev")
    env = raw_env.lower()

    return config.load(config_dir=path, app_env=env)
