"""
Auth handler utilities for fetch_client.
"""
import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, Optional

from ..types import RequestContext
from ..config import AuthConfig

logger = logging.getLogger(__name__)
LOG_PREFIX = f"[AUTH:{__file__}]"


def _mask_value(val: Optional[str]) -> str:
    """Mask sensitive value for logging, showing first 10 chars."""
    if not val:
        return "<empty>"
    if len(val) <= 10:
        return "*" * len(val)
    return val[:10] + "*" * (len(val) - 10)


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
        header = {"Authorization": f"Bearer {key}"}
        logger.debug(
            f"{LOG_PREFIX} BearerAuthHandler.get_header: api_key={_mask_value(key)} -> "
            f"Authorization={_mask_value(header['Authorization'])}"
        )
        return header


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
        logger.debug(f"{LOG_PREFIX} XApiKeyAuthHandler.get_header: api_key={_mask_value(key)}")
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
        logger.debug(
            f"{LOG_PREFIX} CustomAuthHandler.get_header: header_name={self._header_name}, "
            f"api_key={_mask_value(key)}"
        )
        return {self._header_name: key}


def create_auth_handler(config: AuthConfig) -> AuthHandler:
    """Create auth handler from config."""
    # Use raw_api_key (not computed api_key property) as handlers format their own headers
    logger.debug(
        f"{LOG_PREFIX} create_auth_handler: type={config.type}, "
        f"raw_api_key={_mask_value(config.raw_api_key)}, "
        f"email={_mask_value(config.email)}, username={_mask_value(config.username)}"
    )

    if config.type == "bearer":
        logger.debug(f"{LOG_PREFIX} create_auth_handler: Bearer type, using raw_api_key")
        return BearerAuthHandler(config.raw_api_key, config.get_api_key_for_request)
    elif config.type == "x-api-key":
        logger.debug(f"{LOG_PREFIX} create_auth_handler: x-api-key type, using raw_api_key")
        return XApiKeyAuthHandler(config.raw_api_key, config.get_api_key_for_request)
    elif config.type == "custom":
        logger.debug(
            f"{LOG_PREFIX} create_auth_handler: Custom type, header_name={config.header_name}"
        )
        return CustomAuthHandler(
            config.header_name or "Authorization",
            config.raw_api_key,
            config.get_api_key_for_request,
        )
    else:
        logger.debug(
            f"{LOG_PREFIX} create_auth_handler: Unknown type '{config.type}', defaulting to bearer"
        )
        return BearerAuthHandler(config.raw_api_key, config.get_api_key_for_request)
