"""
Tests for ndjson_reader.py
Logic testing: Loop, Boundary, Path, Error Path coverage
"""
import pytest

from fetch_client.streaming.ndjson_reader import (
    parse_ndjson_stream,
    parse_ndjson_stream_sync,
    encode_ndjson,
)
from fetch_client.config import DefaultSerializer


async def create_async_chunks(chunks: list[str]):
    """Create async iterable from string chunks."""
    for chunk in chunks:
        yield chunk.encode("utf-8")


def create_sync_chunks(chunks: list[str]):
    """Create sync iterable from string chunks."""
    for chunk in chunks:
        yield chunk.encode("utf-8")


class TestParseNdjsonStream:
    """Tests for parse_ndjson_stream function."""

    # Happy Path: single object
    @pytest.mark.asyncio
    async def test_single_object(self):
        chunks = ['{"name":"test"}\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 1
        assert objects[0] == {"name": "test"}

    # Loop: multiple objects
    @pytest.mark.asyncio
    async def test_multiple_objects(self):
        chunks = ['{"id":1}\n{"id":2}\n{"id":3}\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 3
        assert objects == [{"id": 1}, {"id": 2}, {"id": 3}]

    # Loop: split across chunks
    @pytest.mark.asyncio
    async def test_split_across_chunks(self):
        chunks = ['{"na', 'me":"te', 'st"}\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 1
        assert objects[0] == {"name": "test"}

    # Boundary: trailing incomplete line
    @pytest.mark.asyncio
    async def test_trailing_line(self):
        chunks = ['{"id":1}\n{"id":2}']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 2
        assert objects[1] == {"id": 2}

    # Path: empty lines skipped
    @pytest.mark.asyncio
    async def test_empty_lines_skipped(self):
        chunks = ['{"id":1}\n\n\n{"id":2}\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 2

    # Path: whitespace-only lines skipped
    @pytest.mark.asyncio
    async def test_whitespace_lines_skipped(self):
        chunks = ['{"id":1}\n   \n{"id":2}\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 2

    # Error Path: malformed line skipped
    @pytest.mark.asyncio
    async def test_malformed_line_skipped(self):
        chunks = ['{"id":1}\nnot json\n{"id":2}\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 2
        assert objects == [{"id": 1}, {"id": 2}]

    # Boundary: empty stream
    @pytest.mark.asyncio
    async def test_empty_stream(self):
        chunks: list[str] = []
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 0

    # Path: custom serializer
    @pytest.mark.asyncio
    async def test_custom_serializer(self):
        class CustomSerializer:
            def deserialize(self, text):
                obj = DefaultSerializer().deserialize(text)
                return {**obj, "customized": True}

            def serialize(self, data):
                return DefaultSerializer().serialize(data)

        chunks = ['{"id":1}\n']
        objects = []

        async for obj in parse_ndjson_stream(
            create_async_chunks(chunks), CustomSerializer()
        ):
            objects.append(obj)

        assert len(objects) == 1
        assert objects[0] == {"id": 1, "customized": True}

    # Path: arrays as top-level
    @pytest.mark.asyncio
    async def test_arrays_top_level(self):
        chunks = ['[1,2,3]\n["a","b"]\n']
        objects = []

        async for obj in parse_ndjson_stream(create_async_chunks(chunks)):
            objects.append(obj)

        assert len(objects) == 2
        assert objects[0] == [1, 2, 3]
        assert objects[1] == ["a", "b"]


class TestParseNdjsonStreamSync:
    """Tests for parse_ndjson_stream_sync function."""

    # Path: uses default serializer
    def test_default_serializer(self):
        chunks = ['{"key":"value"}\n']
        objects = list(parse_ndjson_stream_sync(create_sync_chunks(chunks)))

        assert len(objects) == 1
        assert objects[0] == {"key": "value"}

    # Path: multiple objects
    def test_multiple_objects_sync(self):
        chunks = ['{"a":1}\n{"b":2}\n']
        objects = list(parse_ndjson_stream_sync(create_sync_chunks(chunks)))

        assert len(objects) == 2


class TestEncodeNdjson:
    """Tests for encode_ndjson function."""

    # Boundary: empty array
    def test_empty_array(self):
        result = encode_ndjson([])
        assert result == ""

    # Path: single item
    def test_single_item(self):
        result = encode_ndjson([{"id": 1}])
        assert result == '{"id": 1}'

    # Path: multiple items
    def test_multiple_items(self):
        result = encode_ndjson([{"id": 1}, {"id": 2}, {"id": 3}])
        lines = result.split("\n")

        assert len(lines) == 3

    # Path: custom serializer
    def test_custom_serializer(self):
        class CustomSerializer:
            def serialize(self, obj):
                return DefaultSerializer().serialize(obj).upper()

            def deserialize(self, text):
                return DefaultSerializer().deserialize(text)

        result = encode_ndjson([{"id": 1}], CustomSerializer())
        assert result == '{"ID": 1}'.upper()

    # Path: primitive values
    def test_primitive_values(self):
        result = encode_ndjson([1, "string", True, None])
        lines = result.split("\n")

        assert len(lines) == 4
        assert lines[0] == "1"
        assert lines[1] == '"string"'
        assert lines[2] == "true"
        assert lines[3] == "null"

    # Path: arrays as items
    def test_arrays_as_items(self):
        result = encode_ndjson([[1, 2], [3, 4]])
        assert "[1, 2]" in result
        assert "[3, 4]" in result

    # Boundary: single empty object
    def test_single_empty_object(self):
        result = encode_ndjson([{}])
        assert result == "{}"
