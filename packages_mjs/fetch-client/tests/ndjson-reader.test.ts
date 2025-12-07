/**
 * Tests for ndjson-reader.mts
 * Logic testing: Loop, Boundary, Path, Error Path coverage
 */
import {
  parseNdjsonStream,
  parseNdjsonStreamSimple,
  encodeNdjson,
} from '../src/streaming/ndjson-reader.mjs';
import type { Serializer } from '../src/types.mjs';

describe('ndjson-reader', () => {
  /**
   * Helper to create an async iterable from strings
   */
  async function* createChunks(chunks: string[]): AsyncGenerator<Uint8Array> {
    const encoder = new TextEncoder();
    for (const chunk of chunks) {
      yield encoder.encode(chunk);
    }
  }

  const defaultSerializer: Serializer = {
    serialize: JSON.stringify,
    deserialize: JSON.parse,
  };

  describe('parseNdjsonStream', () => {
    // Happy Path: single object
    it('should parse single NDJSON object', async () => {
      const chunks = ['{"name":"test"}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(1);
      expect(objects[0]).toEqual({ name: 'test' });
    });

    // Loop: multiple objects
    it('should parse multiple NDJSON objects', async () => {
      const chunks = ['{"id":1}\n{"id":2}\n{"id":3}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(3);
      expect(objects).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
    });

    // Loop: split across chunks
    it('should handle object split across chunks', async () => {
      const chunks = ['{"na', 'me":"te', 'st"}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(1);
      expect(objects[0]).toEqual({ name: 'test' });
    });

    // Boundary: trailing incomplete line
    it('should parse trailing line without newline', async () => {
      const chunks = ['{"id":1}\n{"id":2}'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
      expect(objects[1]).toEqual({ id: 2 });
    });

    // Path: empty lines skipped
    it('should skip empty lines', async () => {
      const chunks = ['{"id":1}\n\n\n{"id":2}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
    });

    // Path: whitespace-only lines skipped
    it('should skip whitespace-only lines', async () => {
      const chunks = ['{"id":1}\n   \n{"id":2}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
    });

    // Error Path: malformed line skipped
    it('should skip malformed lines without throwing', async () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      const chunks = ['{"id":1}\nnot json\n{"id":2}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
      expect(objects).toEqual([{ id: 1 }, { id: 2 }]);
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    // Error Path: malformed trailing line silently skipped
    it('should silently skip malformed trailing line', async () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      const chunks = ['{"id":1}\ninvalid'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(1);
      consoleSpy.mockRestore();
    });

    // Boundary: empty stream
    it('should yield nothing for empty stream', async () => {
      const chunks: string[] = [];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(0);
    });

    // Path: custom serializer
    it('should use custom serializer', async () => {
      const customSerializer: Serializer = {
        serialize: JSON.stringify,
        deserialize: (str: string) => {
          const obj = JSON.parse(str);
          return { ...obj, customized: true };
        },
      };

      const chunks = ['{"id":1}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), customSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(1);
      expect(objects[0]).toEqual({ id: 1, customized: true });
    });

    // Path: complex nested objects
    it('should parse complex nested objects', async () => {
      const data = { outer: { inner: { array: [1, 2, 3], bool: true, nil: null } } };
      const chunks = [JSON.stringify(data) + '\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(1);
      expect(objects[0]).toEqual(data);
    });

    // Path: arrays as top-level
    it('should parse arrays as top-level objects', async () => {
      const chunks = ['[1,2,3]\n["a","b"]\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
      expect(objects[0]).toEqual([1, 2, 3]);
      expect(objects[1]).toEqual(['a', 'b']);
    });

    // Boundary: single newline only
    it('should handle single newline only', async () => {
      const chunks = ['\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(0);
    });

    // Path: mixed valid and empty lines
    it('should handle mixed valid and empty lines', async () => {
      const chunks = ['\n{"id":1}\n\n{"id":2}\n\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStream(createChunks(chunks), defaultSerializer)) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
    });
  });

  describe('parseNdjsonStreamSimple', () => {
    // Path: uses default JSON serializer
    it('should parse using default JSON serializer', async () => {
      const chunks = ['{"key":"value"}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStreamSimple(createChunks(chunks))) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(1);
      expect(objects[0]).toEqual({ key: 'value' });
    });

    // Path: multiple objects
    it('should parse multiple objects with default serializer', async () => {
      const chunks = ['{"a":1}\n{"b":2}\n'];
      const objects: unknown[] = [];

      for await (const obj of parseNdjsonStreamSimple(createChunks(chunks))) {
        objects.push(obj);
      }

      expect(objects).toHaveLength(2);
    });
  });

  describe('encodeNdjson', () => {
    // Boundary: empty array
    it('should return empty string for empty array', () => {
      const result = encodeNdjson([]);
      expect(result).toBe('');
    });

    // Path: single item
    it('should encode single item', () => {
      const result = encodeNdjson([{ id: 1 }]);
      expect(result).toBe('{"id":1}');
    });

    // Path: multiple items
    it('should encode multiple items with newline separator', () => {
      const result = encodeNdjson([{ id: 1 }, { id: 2 }, { id: 3 }]);
      expect(result).toBe('{"id":1}\n{"id":2}\n{"id":3}');
    });

    // Path: custom serializer
    it('should use custom serializer', () => {
      const customSerializer: Serializer = {
        serialize: (obj) => JSON.stringify(obj).toUpperCase(),
        deserialize: JSON.parse,
      };

      const result = encodeNdjson([{ id: 1 }], customSerializer);
      expect(result).toBe('{"ID":1}'.toUpperCase());
    });

    // Path: complex objects
    it('should encode complex nested objects', () => {
      const items = [
        { outer: { inner: [1, 2] } },
        { array: [{ nested: true }] },
      ];
      const result = encodeNdjson(items);
      const lines = result.split('\n');

      expect(lines).toHaveLength(2);
      expect(JSON.parse(lines[0])).toEqual(items[0]);
      expect(JSON.parse(lines[1])).toEqual(items[1]);
    });

    // Path: primitive values
    it('should encode primitive values', () => {
      const result = encodeNdjson([1, 'string', true, null]);
      const lines = result.split('\n');

      expect(lines).toHaveLength(4);
      expect(lines[0]).toBe('1');
      expect(lines[1]).toBe('"string"');
      expect(lines[2]).toBe('true');
      expect(lines[3]).toBe('null');
    });

    // Path: arrays as items
    it('should encode arrays as items', () => {
      const result = encodeNdjson([[1, 2], [3, 4]]);
      expect(result).toBe('[1,2]\n[3,4]');
    });

    // Boundary: single empty object
    it('should encode single empty object', () => {
      const result = encodeNdjson([{}]);
      expect(result).toBe('{}');
    });

    // Path: default serializer when not provided
    it('should use default serializer when not provided', () => {
      const result = encodeNdjson([{ test: true }]);
      expect(result).toBe('{"test":true}');
    });
  });
});
