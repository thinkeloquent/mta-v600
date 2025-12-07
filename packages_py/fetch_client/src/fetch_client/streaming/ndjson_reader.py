"""
Newline-Delimited JSON (NDJSON) stream parser.
"""
from typing import Any, AsyncGenerator, Generator, Iterable, AsyncIterable, List

from ..config import DefaultSerializer


async def parse_ndjson_stream(
    body: AsyncIterable[bytes],
    serializer: Any = None,
) -> AsyncGenerator[Any, None]:
    """
    Parse NDJSON stream from an async iterable body.

    Args:
        body: Async iterable of bytes (httpx response stream).
        serializer: JSON serializer/deserializer.

    Yields:
        Parsed JSON objects.
    """
    if serializer is None:
        serializer = DefaultSerializer()

    buffer = ""

    async for chunk in body:
        buffer += chunk.decode("utf-8", errors="replace")

        # Split on newlines
        lines = buffer.split("\n")

        # Keep the last line in buffer (may be incomplete)
        buffer = lines.pop() if lines else ""

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            try:
                parsed = serializer.deserialize(trimmed)
                yield parsed
            except Exception:
                # Skip malformed lines
                pass

    # Handle any remaining data
    trimmed = buffer.strip()
    if trimmed:
        try:
            parsed = serializer.deserialize(trimmed)
            yield parsed
        except Exception:
            pass


def parse_ndjson_stream_sync(
    body: Iterable[bytes],
    serializer: Any = None,
) -> Generator[Any, None, None]:
    """
    Parse NDJSON stream from a sync iterable body.

    Args:
        body: Iterable of bytes (httpx response stream).
        serializer: JSON serializer/deserializer.

    Yields:
        Parsed JSON objects.
    """
    if serializer is None:
        serializer = DefaultSerializer()

    buffer = ""

    for chunk in body:
        buffer += chunk.decode("utf-8", errors="replace")

        # Split on newlines
        lines = buffer.split("\n")

        # Keep the last line in buffer (may be incomplete)
        buffer = lines.pop() if lines else ""

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            try:
                parsed = serializer.deserialize(trimmed)
                yield parsed
            except Exception:
                # Skip malformed lines
                pass

    # Handle any remaining data
    trimmed = buffer.strip()
    if trimmed:
        try:
            parsed = serializer.deserialize(trimmed)
            yield parsed
        except Exception:
            pass


def encode_ndjson(items: List[Any], serializer: Any = None) -> str:
    """
    Encode objects as NDJSON.

    Args:
        items: Items to encode.
        serializer: JSON serializer.

    Returns:
        NDJSON string.
    """
    if serializer is None:
        serializer = DefaultSerializer()

    return "\n".join(serializer.serialize(item) for item in items)
