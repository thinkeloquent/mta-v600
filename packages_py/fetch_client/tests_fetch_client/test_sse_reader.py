"""
Tests for sse_reader.py
Logic testing: Decision/Branch, Loop, Boundary, Path coverage
"""
import pytest

from fetch_client.streaming.sse_reader import (
    parse_sse_stream,
    parse_sse_stream_sync,
    parse_sse_event,
    parse_sse_data,
)
from fetch_client.types import SSEEvent


async def create_async_chunks(chunks: list[str]):
    """Create async iterable from string chunks."""
    for chunk in chunks:
        yield chunk.encode("utf-8")


def create_sync_chunks(chunks: list[str]):
    """Create sync iterable from string chunks."""
    for chunk in chunks:
        yield chunk.encode("utf-8")


class TestParseSSEStream:
    """Tests for parse_sse_stream function."""

    # Happy Path: single event
    @pytest.mark.asyncio
    async def test_single_event(self):
        chunks = ["data: hello world\n\n"]
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 1
        assert events[0].data == "hello world"

    # Loop: multiple events
    @pytest.mark.asyncio
    async def test_multiple_events(self):
        chunks = ["data: first\n\ndata: second\n\ndata: third\n\n"]
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 3
        assert events[0].data == "first"
        assert events[1].data == "second"
        assert events[2].data == "third"

    # Loop: event split across chunks
    @pytest.mark.asyncio
    async def test_split_across_chunks(self):
        chunks = ["data: hel", "lo wor", "ld\n\n"]
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 1
        assert events[0].data == "hello world"

    # Boundary: trailing incomplete event
    @pytest.mark.asyncio
    async def test_trailing_buffer(self):
        chunks = ["data: event1\n\ndata: event2"]
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 2
        assert events[0].data == "event1"
        assert events[1].data == "event2"

    # Boundary: empty stream
    @pytest.mark.asyncio
    async def test_empty_stream(self):
        chunks: list[str] = []
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 0

    # Path: multiple data lines
    @pytest.mark.asyncio
    async def test_multiline_data(self):
        chunks = ["data: line1\ndata: line2\ndata: line3\n\n"]
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 1
        assert events[0].data == "line1\nline2\nline3"

    # Path: event with all fields
    @pytest.mark.asyncio
    async def test_all_fields(self):
        chunks = ["event: message\nid: 123\nretry: 5000\ndata: payload\n\n"]
        events = []

        async for event in parse_sse_stream(create_async_chunks(chunks)):
            events.append(event)

        assert len(events) == 1
        assert events[0].event == "message"
        assert events[0].id == "123"
        assert events[0].retry == 5000
        assert events[0].data == "payload"


class TestParseSSEStreamSync:
    """Tests for parse_sse_stream_sync function."""

    # Path: single event sync
    def test_single_event_sync(self):
        chunks = ["data: hello sync\n\n"]
        events = list(parse_sse_stream_sync(create_sync_chunks(chunks)))

        assert len(events) == 1
        assert events[0].data == "hello sync"

    # Loop: multiple events sync
    def test_multiple_events_sync(self):
        chunks = ["data: a\n\ndata: b\n\n"]
        events = list(parse_sse_stream_sync(create_sync_chunks(chunks)))

        assert len(events) == 2


class TestParseSSEEvent:
    """Tests for parse_sse_event function."""

    # Path: data field
    def test_parse_data_field(self):
        result = parse_sse_event("data: hello")

        assert result is not None
        assert result.data == "hello"

    # Path: id field
    def test_parse_id_field(self):
        result = parse_sse_event("id: 123\ndata: test")

        assert result is not None
        assert result.id == "123"

    # Path: event field
    def test_parse_event_field(self):
        result = parse_sse_event("event: custom\ndata: test")

        assert result is not None
        assert result.event == "custom"

    # Path: retry field as number
    def test_parse_retry_field(self):
        result = parse_sse_event("retry: 3000\ndata: test")

        assert result is not None
        assert result.retry == 3000

    # Path: invalid retry value
    def test_parse_invalid_retry(self):
        result = parse_sse_event("retry: invalid\ndata: test")

        assert result is not None
        assert result.retry is None

    # Path: multi-line data
    def test_parse_multiline_data(self):
        result = parse_sse_event("data: line1\ndata: line2\ndata: line3")

        assert result is not None
        assert result.data == "line1\nline2\nline3"

    # Path: comment lines ignored
    def test_ignore_comments(self):
        result = parse_sse_event(": this is a comment\ndata: actual data")

        assert result is not None
        assert result.data == "actual data"

    # Boundary: missing colon
    def test_skip_no_colon(self):
        result = parse_sse_event("invalid line\ndata: valid")

        assert result is not None
        assert result.data == "valid"

    # Path: space after colon trimmed
    def test_space_after_colon(self):
        result = parse_sse_event("data: with space")

        assert result is not None
        assert result.data == "with space"

    # Path: no space after colon
    def test_no_space_after_colon(self):
        result = parse_sse_event("data:no space")

        assert result is not None
        assert result.data == "no space"

    # Boundary: no data or event - returns None
    def test_no_data_or_event(self):
        result = parse_sse_event(": just a comment")

        assert result is None

    # Path: event without data
    def test_event_without_data(self):
        result = parse_sse_event("event: ping")

        assert result is not None
        assert result.event == "ping"
        assert result.data == ""

    # Boundary: empty string
    def test_empty_string(self):
        result = parse_sse_event("")

        assert result is None


class TestParseSSEData:
    """Tests for parse_sse_data function."""

    # Path: valid JSON
    def test_valid_json(self):
        event = SSEEvent(data='{"name":"test","value":123}')
        result = parse_sse_data(event)

        assert result == {"name": "test", "value": 123}

    # Error Path: invalid JSON
    def test_invalid_json(self):
        event = SSEEvent(data="not json")
        result = parse_sse_data(event)

        assert result is None

    # Decision: [DONE] marker
    def test_done_marker(self):
        event = SSEEvent(data="[DONE]")
        result = parse_sse_data(event)

        assert result is None

    # Decision: [DONE] with whitespace
    def test_done_marker_whitespace(self):
        event = SSEEvent(data="  [DONE]  ")
        result = parse_sse_data(event)

        assert result is None

    # Boundary: empty data
    def test_empty_data(self):
        event = SSEEvent(data="")
        result = parse_sse_data(event)

        assert result is None

    # Path: nested JSON
    def test_nested_json(self):
        event = SSEEvent(data='{"outer":{"inner":{"deep":"value"}}}')
        result = parse_sse_data(event)

        assert result == {"outer": {"inner": {"deep": "value"}}}

    # Path: JSON array
    def test_json_array(self):
        event = SSEEvent(data="[1,2,3]")
        result = parse_sse_data(event)

        assert result == [1, 2, 3]

    # Path: JSON null
    def test_json_null(self):
        event = SSEEvent(data="null")
        result = parse_sse_data(event)

        assert result is None
