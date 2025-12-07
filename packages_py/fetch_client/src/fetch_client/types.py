"""
Type definitions for fetch_client.
"""
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    Union,
)
from dataclasses import dataclass


# Auth types
AuthType = Literal["bearer", "x-api-key", "custom"]

# Stream formats
StreamFormat = Literal["sse", "ndjson", False]

# Protocol types
ProtocolType = Literal["rest", "rpc"]

# HTTP methods
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


@dataclass
class RequestContext:
    """Request context passed to auth callback."""

    method: HttpMethod
    path: str
    headers: Optional[Dict[str, str]] = None
    json: Optional[Any] = None


@dataclass
class SSEEvent:
    """Server-Sent Event structure."""

    data: str
    id: Optional[str] = None
    event: Optional[str] = None
    retry: Optional[int] = None


class FetchResponse(TypedDict):
    """Response from fetch client."""

    status: int
    status_text: str
    headers: Dict[str, str]
    data: Any
    ok: bool


class RequestOptions(TypedDict, total=False):
    """Request options for fetch client."""

    method: HttpMethod
    path: str
    headers: Dict[str, str]
    json: Any
    body: Union[str, bytes]
    query: Dict[str, Union[str, int, bool]]
    timeout: float


class StreamOptions(RequestOptions, total=False):
    """Stream options."""

    on_event: Callable[[SSEEvent], None]


class DiagnosticsEvent(TypedDict, total=False):
    """Diagnostics event structure."""

    name: str
    timestamp: float
    duration: float
    request: Dict[str, Any]
    response: Dict[str, Any]
    error: Optional[Exception]


class Serializer(Protocol):
    """Serializer protocol for custom JSON handling."""

    def serialize(self, data: Any) -> str:
        """Serialize data to string."""
        ...

    def deserialize(self, text: str) -> Any:
        """Deserialize string to data."""
        ...


class FetchClientProtocol(Protocol):
    """Fetch client interface."""

    async def get(
        self, path: str, **kwargs: Any
    ) -> FetchResponse:
        """GET request."""
        ...

    async def post(
        self, path: str, **kwargs: Any
    ) -> FetchResponse:
        """POST request."""
        ...

    async def put(
        self, path: str, **kwargs: Any
    ) -> FetchResponse:
        """PUT request."""
        ...

    async def patch(
        self, path: str, **kwargs: Any
    ) -> FetchResponse:
        """PATCH request."""
        ...

    async def delete(
        self, path: str, **kwargs: Any
    ) -> FetchResponse:
        """DELETE request."""
        ...

    async def request(
        self, **kwargs: Any
    ) -> FetchResponse:
        """Generic request."""
        ...

    def stream(
        self, path: str, **kwargs: Any
    ) -> AsyncGenerator[SSEEvent, None]:
        """Stream SSE response."""
        ...

    def stream_ndjson(
        self, path: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """Stream NDJSON response."""
        ...

    async def close(self) -> None:
        """Close the client."""
        ...
