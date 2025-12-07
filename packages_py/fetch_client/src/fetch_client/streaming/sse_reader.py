"""
Server-Sent Events (SSE) stream parser.
"""
from typing import Any, AsyncGenerator, Generator, Iterable, AsyncIterable, Optional

from ..types import SSEEvent


async def parse_sse_stream(
    body: AsyncIterable[bytes],
) -> AsyncGenerator[SSEEvent, None]:
    """
    Parse SSE stream from an async iterable body.

    Args:
        body: Async iterable of bytes (httpx response stream).

    Yields:
        SSEEvent objects.
    """
    buffer = ""

    async for chunk in body:
        buffer += chunk.decode("utf-8", errors="replace")

        # Split on double newlines (SSE event delimiter)
        parts = buffer.split("\n\n")

        # Keep the last part in buffer (may be incomplete)
        buffer = parts.pop() if parts else ""

        for part in parts:
            event = parse_sse_event(part)
            if event:
                yield event

    # Handle any remaining data
    if buffer.strip():
        event = parse_sse_event(buffer)
        if event:
            yield event


def parse_sse_stream_sync(
    body: Iterable[bytes],
) -> Generator[SSEEvent, None, None]:
    """
    Parse SSE stream from a sync iterable body.

    Args:
        body: Iterable of bytes (httpx response stream).

    Yields:
        SSEEvent objects.
    """
    buffer = ""

    for chunk in body:
        buffer += chunk.decode("utf-8", errors="replace")

        # Split on double newlines (SSE event delimiter)
        parts = buffer.split("\n\n")

        # Keep the last part in buffer (may be incomplete)
        buffer = parts.pop() if parts else ""

        for part in parts:
            event = parse_sse_event(part)
            if event:
                yield event

    # Handle any remaining data
    if buffer.strip():
        event = parse_sse_event(buffer)
        if event:
            yield event


def parse_sse_event(text: str) -> Optional[SSEEvent]:
    """
    Parse a single SSE event from text.

    Args:
        text: Raw SSE event text.

    Returns:
        Parsed SSEEvent or None if invalid.
    """
    lines = text.split("\n")
    data_lines: list[str] = []
    event_type: Optional[str] = None
    event_id: Optional[str] = None
    retry: Optional[int] = None

    for line in lines:
        if line.startswith(":"):
            # Comment line, ignore
            continue

        colon_index = line.find(":")
        if colon_index == -1:
            # Field with no value
            continue

        field = line[:colon_index]
        # Value starts after colon, strip leading space if present
        value = line[colon_index + 1:]
        if value.startswith(" "):
            value = value[1:]

        if field == "event":
            event_type = value
        elif field == "id":
            event_id = value
        elif field == "retry":
            try:
                retry = int(value)
            except ValueError:
                pass
        elif field == "data":
            data_lines.append(value)

    # Join data lines with newlines
    data = "\n".join(data_lines)

    # Return None if no data
    if not data and not event_type:
        return None

    return SSEEvent(
        data=data,
        id=event_id,
        event=event_type,
        retry=retry,
    )


def parse_sse_data(event: SSEEvent) -> Optional[Any]:
    """
    Parse SSE data field as JSON.

    Args:
        event: SSE event.

    Returns:
        Parsed JSON data or None if parsing fails.
    """
    import json

    if not event.data:
        return None

    # Handle [DONE] marker (common in OpenAI-style streams)
    if event.data.strip() == "[DONE]":
        return None

    try:
        return json.loads(event.data)
    except Exception:
        return None
