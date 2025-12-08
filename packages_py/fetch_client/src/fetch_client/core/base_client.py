"""
Base HTTP client using httpx.
"""
import logging
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Union

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
import json

from ..types import FetchResponse, HttpMethod, RequestContext, SSEEvent
from ..config import ClientConfig, resolve_config, ResolvedConfig
from .request_builder import (
    build_url,
    build_headers,
    build_body,
    create_request_context,
)
from ..streaming.sse_reader import parse_sse_stream, parse_sse_stream_sync
from ..streaming.ndjson_reader import parse_ndjson_stream, parse_ndjson_stream_sync

logger = logging.getLogger("fetch_client.base_client")

# Rich console for pretty printing
console = Console()


def _mask_auth_header(headers: Dict[str, str]) -> Dict[str, str]:
    """Mask authorization header for safe logging."""
    masked = dict(headers)
    for key in masked:
        if key.lower() in ('authorization', 'x-api-key'):
            value = masked[key]
            if len(value) > 10:
                masked[key] = value[:10] + '*' * (len(value) - 10)
            else:
                masked[key] = '*' * len(value)
    return masked


def _format_body(body: Any) -> str:
    """Format body for pretty printing."""
    if body is None:
        return ""
    if isinstance(body, (dict, list)):
        return json.dumps(body, indent=2, ensure_ascii=False)
    if isinstance(body, bytes):
        try:
            return body.decode('utf-8')
        except UnicodeDecodeError:
            return f"<binary data: {len(body)} bytes>"
    return str(body)


class AsyncFetchClient:
    """Asynchronous HTTP client implementation."""

    def __init__(
        self,
        config: ClientConfig,
        httpx_client: Optional[httpx.AsyncClient] = None,
    ):
        self._config = resolve_config(config)
        self._client = httpx_client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self._config.timeout.connect,
                read=self._config.timeout.read,
                write=self._config.timeout.write,
                pool=self._config.timeout.connect,
            ),
        )
        self._closed = False

    async def request(
        self,
        method: HttpMethod = "GET",
        path: str = "/",
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        body: Optional[Union[str, bytes]] = None,
        query: Optional[Dict[str, Union[str, int, bool]]] = None,
        timeout: Optional[float] = None,
    ) -> FetchResponse:
        """Make a generic HTTP request."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        url = build_url(self._config.base_url, path, query)
        context = create_request_context(method, path, headers, json)
        has_body = json is not None or body is not None

        logger.debug(f"AsyncFetchClient.request: method={method}, path={path}, base_url={self._config.base_url}")
        logger.debug(f"AsyncFetchClient.request: built url={url}")
        logger.debug(f"AsyncFetchClient.request: config.auth={self._config.auth}")
        logger.debug(f"AsyncFetchClient.request: context={context}")

        request_headers = build_headers(self._config, headers, context, has_body)
        request_body = build_body(json, body, self._config.serializer)

        # Pretty print request
        masked_headers = _mask_auth_header(request_headers)
        request_info = f"[bold cyan]{method}[/bold cyan] {url}"
        console.print(Panel(request_info, title="[bold blue]Request[/bold blue]", expand=False))
        console.print("[bold]Headers:[/bold]", masked_headers)
        if json is not None:
            body_str = _format_body(json)
            console.print(Panel(Syntax(body_str, "json", theme="monokai"), title="[bold]Request Body[/bold]", expand=False))

        response = await self._client.request(
            method=method,
            url=url,
            headers=request_headers,
            content=request_body,
            timeout=timeout,
        )

        response_headers = dict(response.headers)
        text = response.text

        try:
            data = self._config.serializer.deserialize(text)
        except Exception:
            data = text

        # Pretty print response
        status_color = "green" if 200 <= response.status_code < 300 else "red"
        response_info = f"[bold {status_color}]{response.status_code}[/bold {status_color}] {response.reason_phrase or ''}"
        console.print(Panel(response_info, title="[bold blue]Response[/bold blue]", expand=False))
        console.print("[bold]Headers:[/bold]", dict(response_headers))
        if data:
            body_str = _format_body(data)
            console.print(Panel(Syntax(body_str, "json", theme="monokai"), title="[bold]Response Body[/bold]", expand=False))

        return FetchResponse(
            status=response.status_code,
            status_text=response.reason_phrase or "",
            headers=response_headers,
            data=data,
            ok=200 <= response.status_code < 300,
        )

    async def get(self, path: str, **kwargs: Any) -> FetchResponse:
        """GET request."""
        return await self.request(method="GET", path=path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> FetchResponse:
        """POST request."""
        return await self.request(method="POST", path=path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> FetchResponse:
        """PUT request."""
        return await self.request(method="PUT", path=path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> FetchResponse:
        """PATCH request."""
        return await self.request(method="PATCH", path=path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> FetchResponse:
        """DELETE request."""
        return await self.request(method="DELETE", path=path, **kwargs)

    async def stream(
        self,
        path: str,
        method: HttpMethod = "POST",
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        query: Optional[Dict[str, Union[str, int, bool]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Stream SSE response."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        url = build_url(self._config.base_url, path, query)
        context = create_request_context(method, path, headers, json)
        has_body = json is not None

        request_headers = build_headers(self._config, headers, context, has_body)
        request_headers["accept"] = "text/event-stream"
        request_body = build_body(json, None, self._config.serializer)

        async with self._client.stream(
            method=method,
            url=url,
            headers=request_headers,
            content=request_body,
        ) as response:
            if not (200 <= response.status_code < 300):
                text = await response.aread()
                raise RuntimeError(f"HTTP {response.status_code}: {text.decode()}")

            async for event in parse_sse_stream(response.aiter_bytes()):
                yield event

    async def stream_ndjson(
        self,
        path: str,
        method: HttpMethod = "GET",
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        query: Optional[Dict[str, Union[str, int, bool]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """Stream NDJSON response."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        url = build_url(self._config.base_url, path, query)
        context = create_request_context(method, path, headers, json)
        has_body = json is not None

        request_headers = build_headers(self._config, headers, context, has_body)
        request_headers["accept"] = "application/x-ndjson"
        request_body = build_body(json, None, self._config.serializer)

        async with self._client.stream(
            method=method,
            url=url,
            headers=request_headers,
            content=request_body,
        ) as response:
            if not (200 <= response.status_code < 300):
                text = await response.aread()
                raise RuntimeError(f"HTTP {response.status_code}: {text.decode()}")

            async for item in parse_ndjson_stream(
                response.aiter_bytes(), self._config.serializer
            ):
                yield item

    async def close(self) -> None:
        """Close the client."""
        self._closed = True
        await self._client.aclose()


class SyncFetchClient:
    """Synchronous HTTP client implementation."""

    def __init__(
        self,
        config: ClientConfig,
        httpx_client: Optional[httpx.Client] = None,
    ):
        self._config = resolve_config(config)
        self._client = httpx_client or httpx.Client(
            timeout=httpx.Timeout(
                connect=self._config.timeout.connect,
                read=self._config.timeout.read,
                write=self._config.timeout.write,
                pool=self._config.timeout.connect,
            ),
        )
        self._closed = False

    def request(
        self,
        method: HttpMethod = "GET",
        path: str = "/",
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        body: Optional[Union[str, bytes]] = None,
        query: Optional[Dict[str, Union[str, int, bool]]] = None,
        timeout: Optional[float] = None,
    ) -> FetchResponse:
        """Make a generic HTTP request."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        url = build_url(self._config.base_url, path, query)
        context = create_request_context(method, path, headers, json)
        has_body = json is not None or body is not None

        request_headers = build_headers(self._config, headers, context, has_body)
        request_body = build_body(json, body, self._config.serializer)

        # Pretty print request
        masked_headers = _mask_auth_header(request_headers)
        request_info = f"[bold cyan]{method}[/bold cyan] {url}"
        console.print(Panel(request_info, title="[bold blue]Request[/bold blue]", expand=False))
        console.print("[bold]Headers:[/bold]", masked_headers)
        if json is not None:
            body_str = _format_body(json)
            console.print(Panel(Syntax(body_str, "json", theme="monokai"), title="[bold]Request Body[/bold]", expand=False))

        response = self._client.request(
            method=method,
            url=url,
            headers=request_headers,
            content=request_body,
            timeout=timeout,
        )

        response_headers = dict(response.headers)
        text = response.text

        try:
            data = self._config.serializer.deserialize(text)
        except Exception:
            data = text

        # Pretty print response
        status_color = "green" if 200 <= response.status_code < 300 else "red"
        response_info = f"[bold {status_color}]{response.status_code}[/bold {status_color}] {response.reason_phrase or ''}"
        console.print(Panel(response_info, title="[bold blue]Response[/bold blue]", expand=False))
        console.print("[bold]Headers:[/bold]", dict(response_headers))
        if data:
            body_str = _format_body(data)
            console.print(Panel(Syntax(body_str, "json", theme="monokai"), title="[bold]Response Body[/bold]", expand=False))

        return FetchResponse(
            status=response.status_code,
            status_text=response.reason_phrase or "",
            headers=response_headers,
            data=data,
            ok=200 <= response.status_code < 300,
        )

    def get(self, path: str, **kwargs: Any) -> FetchResponse:
        """GET request."""
        return self.request(method="GET", path=path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> FetchResponse:
        """POST request."""
        return self.request(method="POST", path=path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> FetchResponse:
        """PUT request."""
        return self.request(method="PUT", path=path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> FetchResponse:
        """PATCH request."""
        return self.request(method="PATCH", path=path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> FetchResponse:
        """DELETE request."""
        return self.request(method="DELETE", path=path, **kwargs)

    def stream(
        self,
        path: str,
        method: HttpMethod = "POST",
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        query: Optional[Dict[str, Union[str, int, bool]]] = None,
        **kwargs: Any,
    ) -> Generator[SSEEvent, None, None]:
        """Stream SSE response."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        url = build_url(self._config.base_url, path, query)
        context = create_request_context(method, path, headers, json)
        has_body = json is not None

        request_headers = build_headers(self._config, headers, context, has_body)
        request_headers["accept"] = "text/event-stream"
        request_body = build_body(json, None, self._config.serializer)

        with self._client.stream(
            method=method,
            url=url,
            headers=request_headers,
            content=request_body,
        ) as response:
            if not (200 <= response.status_code < 300):
                text = response.read()
                raise RuntimeError(f"HTTP {response.status_code}: {text.decode()}")

            yield from parse_sse_stream_sync(response.iter_bytes())

    def stream_ndjson(
        self,
        path: str,
        method: HttpMethod = "GET",
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Any] = None,
        query: Optional[Dict[str, Union[str, int, bool]]] = None,
        **kwargs: Any,
    ) -> Generator[Any, None, None]:
        """Stream NDJSON response."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        url = build_url(self._config.base_url, path, query)
        context = create_request_context(method, path, headers, json)
        has_body = json is not None

        request_headers = build_headers(self._config, headers, context, has_body)
        request_headers["accept"] = "application/x-ndjson"
        request_body = build_body(json, None, self._config.serializer)

        with self._client.stream(
            method=method,
            url=url,
            headers=request_headers,
            content=request_body,
        ) as response:
            if not (200 <= response.status_code < 300):
                text = response.read()
                raise RuntimeError(f"HTTP {response.status_code}: {text.decode()}")

            yield from parse_ndjson_stream_sync(
                response.iter_bytes(), self._config.serializer
            )

    def close(self) -> None:
        """Close the client."""
        self._closed = True
        self._client.close()
