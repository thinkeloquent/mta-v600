"""
Request builder utilities for fetch_client.
"""
import logging
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin, urlparse

from ..types import HttpMethod, RequestContext
from ..config import (
    AuthConfig,
    ResolvedConfig,
    get_auth_header_name,
    format_auth_header_value,
)

logger = logging.getLogger("fetch_client.request_builder")


def build_url(
    base_url: str,
    path: str,
    query: Optional[Dict[str, Union[str, int, bool]]] = None,
) -> str:
    """Build full URL from base and path."""
    # Handle absolute paths - preserve base_url path and append the new path
    if path.startswith("/"):
        parsed = urlparse(base_url)
        # Combine base path with the new path (avoid double slashes)
        base_path = parsed.path.rstrip("/")
        url = f"{parsed.scheme}://{parsed.netloc}{base_path}{path}"
    elif path:
        # urljoin replaces the last segment if base doesn't end with /
        # Ensure base_url ends with / for proper joining with relative paths
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        url = urljoin(base_url, path)
    else:
        # Empty path - use base_url as-is
        url = base_url

    if query:
        query_str = urlencode({k: str(v) for k, v in query.items()})
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query_str}"

    return url


def build_headers(
    config: ResolvedConfig,
    headers: Optional[Dict[str, str]] = None,
    context: Optional[RequestContext] = None,
    has_body: bool = False,
) -> Dict[str, str]:
    """Build request headers."""
    logger.debug(f"build_headers: config.auth={config.auth}, context={context}, has_body={has_body}")
    result = dict(config.headers)

    if headers:
        result.update(headers)

    # Set content-type for requests with body
    if has_body and "content-type" not in {k.lower() for k in result}:
        result["content-type"] = config.content_type

    # Set accept header if not specified
    if "accept" not in {k.lower() for k in result}:
        result["accept"] = "application/json"

    # Apply auth header
    logger.debug(f"build_headers: checking auth - config.auth={config.auth is not None}, context={context is not None}")
    if config.auth and context:
        logger.debug(f"build_headers: calling resolve_auth_header with auth.type={config.auth.type}, auth.raw_api_key={bool(config.auth.raw_api_key)}")
        auth_header = resolve_auth_header(config.auth, context)
        logger.debug(f"build_headers: resolve_auth_header returned={auth_header}")
        if auth_header:
            result.update(auth_header)
    else:
        logger.debug(f"build_headers: skipping auth - config.auth={config.auth}, context={context}")

    return result


def resolve_auth_header(
    auth: AuthConfig,
    context: RequestContext,
) -> Optional[Dict[str, str]]:
    """Resolve auth header from config and context."""
    api_key: Optional[str] = None

    logger.debug(f"resolve_auth_header: auth.type={auth.type}, has_callback={auth.get_api_key_for_request is not None}")

    # Try dynamic callback first
    if auth.get_api_key_for_request:
        api_key = auth.get_api_key_for_request(context)
        logger.debug(f"resolve_auth_header: got key from callback: {bool(api_key)}")

    # Fall back to static key (use raw_api_key, not computed api_key property)
    if not api_key:
        api_key = auth.raw_api_key
        logger.debug(f"resolve_auth_header: using static key: {bool(api_key)}")

    # Check if we have credentials even if api_key is missing
    has_credentials = (
        auth.username is not None or 
        auth.password is not None or 
        auth.email is not None
    )

    if not api_key and not has_credentials:
        logger.debug("resolve_auth_header: no api_key or credentials found, returning None")
        return None
    
    # Use empty string for api_key if only credentials are present
    key_to_use = api_key if api_key is not None else ""

    header_name = get_auth_header_name(auth)
    header_value = format_auth_header_value(auth, key_to_use)

    logger.debug(f"resolve_auth_header: returning header {header_name}=***")
    return {header_name: header_value}


def build_body(
    json_data: Optional[Any] = None,
    body: Optional[Union[str, bytes]] = None,
    serializer: Optional[Any] = None,
) -> Optional[Union[str, bytes]]:
    """Build request body."""
    if body is not None:
        return body

    if json_data is not None and serializer:
        return serializer.serialize(json_data)

    return None


def create_request_context(
    method: HttpMethod,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
) -> RequestContext:
    """Create request context from options."""
    return RequestContext(
        method=method,
        path=path,
        headers=headers,
        json=json_data,
    )
