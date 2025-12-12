"""
Auth Config Resolution Utility.

This is the SINGLE SOURCE OF TRUTH for auth type interpretation.
Used by: factory.py, all standalone health check scripts, CLI tools, SDKs.

The auth resolution logic determines how to configure fetch_client based on
the provider's api_auth_type from YAML config.
"""
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fetch_client import AuthConfig

from console_print import print_auth_trace


def resolve_auth_config(
    auth_type: str,
    api_key_result: Any,
    header_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolve auth configuration from provider auth_type.

    This function determines how to configure fetch_client's AuthConfig based on
    the provider's api_auth_type setting.

    Auth Type Categories:
    ---------------------
    1. Raw Passthrough Types ("custom", "x-api-key"):
       - Pass the raw API key value with a custom header
       - Header name comes from provider config
       - fetch_client uses the value as-is

    2. Bearer Types ("bearer", "bearer_*"):
       - Pass the raw token value
       - fetch_client automatically adds "Bearer " prefix
       - Uses standard Authorization header

    3. Pre-computed Types (all others - "basic", "basic_email_token", etc.):
       - Provider has already computed the full header value
       - e.g., "Basic base64(email:token)"
       - Pass as custom type with the pre-computed value

    Args:
        auth_type: The api_auth_type from provider YAML config
        api_key_result: ApiKeyResult from provider.get_api_key()
        header_name: Header name from provider.get_header_name()

    Returns:
        Dict with keys: type, raw_api_key, header_name (optional)
        Can be passed directly to AuthConfig constructor.

    Example:
        >>> from fetch_client import AuthConfig
        >>> auth_dict = resolve_auth_config("bearer", api_key_result, "Authorization")
        >>> auth_config = AuthConfig(**auth_dict)
    """
    import logging
    logger = logging.getLogger("provider_api_getters.auth_resolver")

    # Debug: Log input values to trace auth issues
    raw_key_preview = getattr(api_key_result, "raw_api_key", None)
    api_key_preview = getattr(api_key_result, "api_key", None)
    print_auth_trace(f"ENTRY auth_type={auth_type}", "auth_resolver.py:65", str(api_key_result))
    logger.debug(
        f"resolve_auth_config: auth_type='{auth_type}', header_name='{header_name}', "
        f"raw_api_key_starts='{raw_key_preview[:20] if raw_key_preview else None}...', "
        f"api_key_starts='{api_key_preview[:20] if api_key_preview else None}...'"
    )
    # Category 1: Raw passthrough - value used as-is with custom header
    raw_passthrough_types = {"custom", "x-api-key"}

    # Category 2: Bearer types - fetch_client adds "Bearer " prefix
    is_bearer_type = auth_type == "bearer" or auth_type.startswith("bearer_")

    if auth_type in raw_passthrough_types:
        # Use raw_api_key if available, fallback to api_key
        raw_key = getattr(api_key_result, "raw_api_key", None) or getattr(api_key_result, "api_key", "")
        print_auth_trace("RETURN (raw_passthrough)", "auth_resolver.py:80", raw_key)
        return {
            "type": "custom",
            "raw_api_key": raw_key,
            "header_name": header_name or "Authorization",
        }

    elif is_bearer_type:
        # Bearer auth: pass raw token, fetch_client adds "Bearer " prefix
        raw_key = getattr(api_key_result, "raw_api_key", None) or getattr(api_key_result, "api_key", "")
        print_auth_trace("RETURN (bearer)", "auth_resolver.py:91", raw_key)
        return {
            "type": "bearer",
            "raw_api_key": raw_key,
        }

    else:
        # Pre-computed value (e.g., "Basic base64(email:token)")
        # Use api_key (not raw_api_key) as it contains the full computed value
        computed_key = getattr(api_key_result, "api_key", "")
        print_auth_trace("RETURN (pre_computed)", "auth_resolver.py:100", computed_key)
        return {
            "type": "custom",
            "raw_api_key": computed_key,
            "header_name": header_name or "Authorization",
        }


def create_auth_config(
    auth_type: str,
    api_key_result: Any,
    header_name: Optional[str] = None,
) -> "AuthConfig":
    """
    Create an AuthConfig instance from provider auth_type.

    Convenience wrapper around resolve_auth_config() that returns
    an AuthConfig instance directly.

    Args:
        auth_type: The api_auth_type from provider YAML config
        api_key_result: ApiKeyResult from provider.get_api_key()
        header_name: Header name from provider.get_header_name()

    Returns:
        AuthConfig instance ready for use with fetch_client
    """
    from fetch_client import AuthConfig

    auth_dict = resolve_auth_config(auth_type, api_key_result, header_name)
    return AuthConfig(**auth_dict)


def get_auth_type_category(auth_type: str) -> str:
    """
    Get the category of an auth type for debugging/logging.

    Args:
        auth_type: The api_auth_type from provider YAML config

    Returns:
        Category string: "raw_passthrough", "bearer", or "pre_computed"
    """
    raw_passthrough_types = {"custom", "x-api-key"}
    is_bearer_type = auth_type == "bearer" or auth_type.startswith("bearer_")

    if auth_type in raw_passthrough_types:
        return "raw_passthrough"
    elif is_bearer_type:
        return "bearer"
    else:
        return "pre_computed"
