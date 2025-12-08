"""
Enterprise-grade HTTP client for Python.

Provides REST-style HTTP methods, streaming (SSE, NDJSON), and multiple auth formats.
Integrates with fetch_proxy_dispatcher for proxy support.
"""
from .types import (
    HttpMethod,
    FetchResponse,
    SSEEvent,
    RequestContext,
    Serializer,
)
from .config import (
    AuthConfig,
    TimeoutConfig,
    ClientConfig,
    DefaultSerializer,
)
from .dns_warmup import warmup_dns, warmup_dns_sync
from .core.base_client import AsyncFetchClient, SyncFetchClient
from .adapters.rest_adapter import AsyncRestAdapter, SyncRestAdapter
from .auth.auth_handler import (
    AuthHandler,
    BearerAuthHandler,
    XApiKeyAuthHandler,
    CustomAuthHandler,
    create_auth_handler,
)
from .streaming.sse_reader import (
    parse_sse_stream,
    parse_sse_stream_sync,
)
from .streaming.ndjson_reader import (
    parse_ndjson_stream,
    parse_ndjson_stream_sync,
    encode_ndjson,
)
from .factory import (
    create_client,
    create_client_with_dispatcher,
    create_async_client,
    create_sync_client,
    create_rest_adapter,
)

__all__ = [
    # Types
    "HttpMethod",
    "FetchResponse",
    "SSEEvent",
    "RequestContext",
    "Serializer",
    # Config
    "AuthConfig",
    "TimeoutConfig",
    "ClientConfig",
    "DefaultSerializer",
    # DNS Warmup
    "warmup_dns",
    "warmup_dns_sync",
    # Clients
    "AsyncFetchClient",
    "SyncFetchClient",
    # Adapters
    "AsyncRestAdapter",
    "SyncRestAdapter",
    # Auth
    "AuthHandler",
    "BearerAuthHandler",
    "XApiKeyAuthHandler",
    "CustomAuthHandler",
    "create_auth_handler",
    # Streaming
    "parse_sse_stream",
    "parse_sse_stream_sync",
    "parse_ndjson_stream",
    "parse_ndjson_stream_sync",
    "encode_ndjson",
    # Factory
    "create_client",
    "create_client_with_dispatcher",
    "create_async_client",
    "create_sync_client",
    "create_rest_adapter",
]

__version__ = "0.1.0"
