"""
Auth handler utilities for fetch_client.
"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional

from ..types import RequestContext
from ..config import AuthConfig


class AuthHandler(ABC):
    """Auth handler interface."""

    @abstractmethod
    def get_header(self, context: RequestContext) -> Optional[Dict[str, str]]:
        """Get auth header for request."""
        ...


class BearerAuthHandler(AuthHandler):
    """Bearer token auth handler."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        get_api_key_for_request: Optional[
            Callable[[RequestContext], Optional[str]]
        ] = None,
    ):
        self._api_key = api_key
        self._get_api_key_for_request = get_api_key_for_request

    def get_header(self, context: RequestContext) -> Optional[Dict[str, str]]:
        """Get bearer auth header."""
        key = None
        if self._get_api_key_for_request:
            key = self._get_api_key_for_request(context)
        if not key:
            key = self._api_key
        if not key:
            return None
        return {"Authorization": f"Bearer {key}"}


class XApiKeyAuthHandler(AuthHandler):
    """X-API-Key auth handler."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        get_api_key_for_request: Optional[
            Callable[[RequestContext], Optional[str]]
        ] = None,
    ):
        self._api_key = api_key
        self._get_api_key_for_request = get_api_key_for_request

    def get_header(self, context: RequestContext) -> Optional[Dict[str, str]]:
        """Get x-api-key auth header."""
        key = None
        if self._get_api_key_for_request:
            key = self._get_api_key_for_request(context)
        if not key:
            key = self._api_key
        if not key:
            return None
        return {"x-api-key": key}


class CustomAuthHandler(AuthHandler):
    """Custom header auth handler."""

    def __init__(
        self,
        header_name: str,
        api_key: Optional[str] = None,
        get_api_key_for_request: Optional[
            Callable[[RequestContext], Optional[str]]
        ] = None,
    ):
        self._header_name = header_name
        self._api_key = api_key
        self._get_api_key_for_request = get_api_key_for_request

    def get_header(self, context: RequestContext) -> Optional[Dict[str, str]]:
        """Get custom auth header."""
        key = None
        if self._get_api_key_for_request:
            key = self._get_api_key_for_request(context)
        if not key:
            key = self._api_key
        if not key:
            return None
        return {self._header_name: key}


def create_auth_handler(config: AuthConfig) -> AuthHandler:
    """Create auth handler from config."""
    # Use raw_api_key (not computed api_key property) as handlers format their own headers
    if config.type == "bearer":
        return BearerAuthHandler(config.raw_api_key, config.get_api_key_for_request)
    elif config.type == "x-api-key":
        return XApiKeyAuthHandler(config.raw_api_key, config.get_api_key_for_request)
    elif config.type == "custom":
        return CustomAuthHandler(
            config.header_name or "Authorization",
            config.raw_api_key,
            config.get_api_key_for_request,
        )
    else:
        return BearerAuthHandler(config.raw_api_key, config.get_api_key_for_request)
