"""
Deep merge utility for provider configuration overrides.

Recursively merges source dict into target dict. Source values
override target values, with nested dicts being merged recursively.
"""

from typing import Any, Dict


def deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries recursively.

    Args:
        target: The base dictionary to merge into
        source: The dictionary with override values

    Returns:
        A new merged dictionary

    Example:
        >>> global_conf = {"proxy": {"cert_verify": True, "proxy_urls": {"dev": "http://dev:8080"}}}
        >>> provider_conf = {"proxy": {"cert_verify": False}}
        >>> merged = deep_merge(global_conf, provider_conf)
        >>> # {"proxy": {"cert_verify": False, "proxy_urls": {"dev": "http://dev:8080"}}}
    """
    # Handle None
    if source is None:
        return target if target is not None else {}
    if target is None:
        return source if source is not None else {}

    # If source is not a dict, return source (override)
    if not isinstance(source, dict):
        return source

    # If target is not a dict, return source
    if not isinstance(target, dict):
        return source

    # Both are dicts, merge recursively
    result = {**target}

    for key, source_value in source.items():
        # Skip None values in source (don't override with None)
        if source_value is None:
            continue

        target_value = result.get(key)

        # Recursively merge nested dicts
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            result[key] = deep_merge(target_value, source_value)
        else:
            # Override with source value
            result[key] = source_value

    return result
