"""
Request builder utilities for fetch_client.
"""
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin, urlparse

from ..types import HttpMethod, RequestContext
from ..config import (
    AuthConfig,
    ResolvedConfig,
    get_auth_header_name,
    format_auth_header_value,
)


def build_url(
    base_url: str,
    path: str,
    query: Optional[Dict[str, Union[str, int, bool]]] = None,
) -> str:
    """Build full URL from base and path."""
    # Handle absolute paths
    if path.startswith("/"):
        parsed = urlparse(base_url)
        url = f"{parsed.scheme}://{parsed.netloc}{path}"
    else:
        url = urljoin(base_url, path)

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
    if config.auth and context:
        auth_header = resolve_auth_header(config.auth, context)
        if auth_header:
            result.update(auth_header)

    return result


def resolve_auth_header(
    auth: AuthConfig,
    context: RequestContext,
) -> Optional[Dict[str, str]]:
    """Resolve auth header from config and context."""
    api_key: Optional[str] = None

    # Try dynamic callback first
    if auth.get_api_key_for_request:
        api_key = auth.get_api_key_for_request(context)

    # Fall back to static key
    if not api_key:
        api_key = auth.api_key

    if not api_key:
        return None

    header_name = get_auth_header_name(auth)
    header_value = format_auth_header_value(auth, api_key)

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
