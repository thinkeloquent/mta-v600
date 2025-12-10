"""
Loader for centralized sensitive test data.

Provides functions to access test data from the YAML configuration file.
Supports both flat key access and dot notation for nested values.

Example:
    from test_sensitive_data import get, get_all, has, get_many

    # Flat access
    email = get('email')

    # Dot notation for nested values
    confluence_email = get('credentials.confluence.email')

    # Check if a key exists
    if has('credentials.jira.token'):
        ...

    # Get multiple values at once
    email, password = get_many('email', 'password')
"""
from pathlib import Path
from typing import Any, List, Optional

import yaml

_data: Optional[dict] = None


def _get_yaml_path() -> Path:
    """Get the path to the YAML data file."""
    return Path(__file__).parent.parent.parent / "sensitive-data.yaml"


def load_data() -> dict:
    """
    Load data from the YAML file (cached after first load).

    Returns:
        The parsed YAML data as a dictionary
    """
    global _data
    if _data is None:
        yaml_path = _get_yaml_path()
        with open(yaml_path, "r", encoding="utf-8") as f:
            _data = yaml.safe_load(f)
    return _data


def get(path: str) -> Any:
    """
    Get a value by key, supporting dot notation for nested values.

    Args:
        path: The key path (e.g., 'email' or 'credentials.confluence.email')

    Returns:
        The value at the path, or None if not found

    Example:
        get('email')                          # 'test@example.com'
        get('credentials.email')              # 'test@example.com'
        get('credentials.confluence.email')   # 'confluence-test@example.com'
        get('nonexistent')                    # None
    """
    data = load_data()

    # Try flat key first
    if "." not in path and path in data:
        return data[path]

    # Try dot notation path
    keys = path.split(".")
    result = data

    for key in keys:
        if result is None:
            return None
        if not isinstance(result, dict):
            return None
        result = result.get(key)

    return result


def get_all() -> dict:
    """
    Get all data as a dictionary.

    Returns:
        The complete data dictionary
    """
    return load_data()


def has(path: str) -> bool:
    """
    Check if a key exists in the data.

    Args:
        path: The key path to check

    Returns:
        True if the key exists and has a non-None value

    Example:
        has('email')                          # True
        has('credentials.confluence.email')   # True
        has('nonexistent')                    # False
    """
    return get(path) is not None


def get_many(*paths: str) -> List[Any]:
    """
    Get multiple values at once.

    Args:
        *paths: The key paths to retrieve

    Returns:
        A list of values in the same order as the paths

    Example:
        email, password = get_many('email', 'password')
        jira_email, jira_token = get_many('credentials.jira.email', 'credentials.jira.token')
    """
    return [get(p) for p in paths]


def get_or_default(path: str, default: Any) -> Any:
    """
    Get a value with a default fallback if the key doesn't exist.

    Args:
        path: The key path
        default: The default value to return if key not found

    Returns:
        The value at the path, or the default value

    Example:
        get_or_default('email', 'fallback@example.com')  # 'test@example.com'
        get_or_default('nonexistent', 'default')         # 'default'
    """
    value = get(path)
    return value if value is not None else default


def _reset_cache() -> None:
    """
    Reset the cached data (useful for testing the loader itself).

    Internal use only.
    """
    global _data
    _data = None
