/**
 * Tests for sse-reader.mts
 * Logic testing: Decision/Branch, Loop, Boundary, Path coverage
 */
import {
  parseSSEStream,
  parseSSEEvent,
  parseSSEData,
} from '../src/streaming/sse-reader.mjs';
import type { SSEEvent } from '../src/types.mjs';
import { Readable } from 'node:stream';

describe('sse-reader', () => {
  /**
   * Helper to create an async iterable from strings
   */
  async function* createChunks(chunks: string[]): AsyncGenerator<Uint8Array> {
    const encoder = new TextEncoder();
    for (const chunk of chunks) {
      yield encoder.encode(chunk);
    }
  }

  describe('parseSSEStream', () => {
    // Happy Path: single event
    it('should parse single complete SSE event', async () => {
      const chunks = ['data: hello world\n\n'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(1);
      expect(events[0].data).toBe('hello world');
    });

    // Loop: multiple events
    it('should parse multiple SSE events', async () => {
      const chunks = ['data: first\n\ndata: second\n\ndata: third\n\n'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(3);
      expect(events[0].data).toBe('first');
      expect(events[1].data).toBe('second');
      expect(events[2].data).toBe('third');
    });

    // Loop: event split across chunks
    it('should handle event split across chunks', async () => {
      const chunks = ['data: hel', 'lo wor', 'ld\n\n'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(1);
      expect(events[0].data).toBe('hello world');
    });

    // Boundary: trailing incomplete event
    it('should flush trailing buffer', async () => {
      const chunks = ['data: event1\n\ndata: event2'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(2);
      expect(events[0].data).toBe('event1');
      expect(events[1].data).toBe('event2');
    });

    // Boundary: empty stream
    it('should yield nothing for empty stream', async () => {
      const chunks: string[] = [];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(0);
    });

    // Path: multiple data lines
    it('should handle multiple data lines as single event', async () => {
      const chunks = ['data: line1\ndata: line2\ndata: line3\n\n'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(1);
      expect(events[0].data).toBe('line1\nline2\nline3');
    });

    // Path: event with all fields
    it('should parse event with all SSE fields', async () => {
      const chunks = ['event: message\nid: 123\nretry: 5000\ndata: payload\n\n'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(1);
      expect(events[0].event).toBe('message');
      expect(events[0].id).toBe('123');
      expect(events[0].retry).toBe(5000);
      expect(events[0].data).toBe('payload');
    });

    // Path: comment-only events filtered
    it('should filter out comment-only events', async () => {
      const chunks = [': this is a comment\n\ndata: real event\n\n'];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(1);
      expect(events[0].data).toBe('real event');
    });

    // Boundary: whitespace only in buffer
    it('should handle whitespace-only trailing buffer', async () => {
      const chunks = ['data: event\n\n   \n   '];
      const events: SSEEvent[] = [];

      for await (const event of parseSSEStream(createChunks(chunks))) {
        events.push(event);
      }

      expect(events).toHaveLength(1);
    });
  });

  describe('parseSSEEvent', () => {
    // Path: data field
    it('should parse data field', () => {
      const result = parseSSEEvent('data: hello');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('hello');
    });

    // Path: id field
    it('should parse id field', () => {
      const result = parseSSEEvent('id: 123\ndata: test');

      expect(result).not.toBeNull();
      expect(result!.id).toBe('123');
    });

    // Path: event field
    it('should parse event type field', () => {
      const result = parseSSEEvent('event: custom\ndata: test');

      expect(result).not.toBeNull();
      expect(result!.event).toBe('custom');
    });

    // Path: retry field as number
    it('should parse retry field as number', () => {
      const result = parseSSEEvent('retry: 3000\ndata: test');

      expect(result).not.toBeNull();
      expect(result!.retry).toBe(3000);
    });

    // Path: multi-line data
    it('should join multi-line data with newlines', () => {
      const result = parseSSEEvent('data: line1\ndata: line2\ndata: line3');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('line1\nline2\nline3');
    });

    // Path: comment lines ignored
    it('should ignore comment lines', () => {
      const result = parseSSEEvent(': this is a comment\ndata: actual data');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('actual data');
    });

    // Boundary: missing colon
    it('should skip lines without colon', () => {
      const result = parseSSEEvent('invalid line\ndata: valid');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('valid');
    });

    // Path: space after colon trimmed
    it('should trim space after colon', () => {
      const result = parseSSEEvent('data: with space');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('with space');
    });

    // Path: no space after colon
    it('should handle no space after colon', () => {
      const result = parseSSEEvent('data:no space');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('no space');
    });

    // Boundary: no data or event - returns null
    it('should return null when no data or event', () => {
      const result = parseSSEEvent(': just a comment');

      expect(result).toBeNull();
    });

    // Path: event without data
    it('should return event with event type but empty data', () => {
      const result = parseSSEEvent('event: ping');

      expect(result).not.toBeNull();
      expect(result!.event).toBe('ping');
      expect(result!.data).toBe('');
    });

    // Boundary: empty string
    it('should return null for empty string', () => {
      const result = parseSSEEvent('');

      expect(result).toBeNull();
    });

    // Path: all fields together
    it('should parse all fields together', () => {
      const result = parseSSEEvent('event: message\nid: 42\nretry: 1000\ndata: payload');

      expect(result).not.toBeNull();
      expect(result!.event).toBe('message');
      expect(result!.id).toBe('42');
      expect(result!.retry).toBe(1000);
      expect(result!.data).toBe('payload');
    });

    // Path: empty data value
    it('should handle empty data value', () => {
      const result = parseSSEEvent('data:');

      expect(result).not.toBeNull();
      expect(result!.data).toBe('');
    });

    // Boundary: field name only
    it('should handle field name with colon but empty value', () => {
      const result = parseSSEEvent('event:\ndata: test');

      expect(result).not.toBeNull();
      expect(result!.event).toBe('');
      expect(result!.data).toBe('test');
    });
  });

  describe('parseSSEData', () => {
    // Path: valid JSON
    it('should parse valid JSON data', () => {
      const event: SSEEvent = { data: '{"name":"test","value":123}' };
      const result = parseSSEData<{ name: string; value: number }>(event);

      expect(result).toEqual({ name: 'test', value: 123 });
    });

    // Error Path: invalid JSON
    it('should return null for invalid JSON', () => {
      const event: SSEEvent = { data: 'not json' };
      const result = parseSSEData(event);

      expect(result).toBeNull();
    });

    // Decision: [DONE] marker
    it('should return null for [DONE] marker', () => {
      const event: SSEEvent = { data: '[DONE]' };
      const result = parseSSEData(event);

      expect(result).toBeNull();
    });

    // Decision: [DONE] with whitespace
    it('should return null for [DONE] marker with whitespace', () => {
      const event: SSEEvent = { data: '  [DONE]  ' };
      const result = parseSSEData(event);

      expect(result).toBeNull();
    });

    // Boundary: empty data
    it('should return null for empty data', () => {
      const event: SSEEvent = { data: '' };
      const result = parseSSEData(event);

      expect(result).toBeNull();
    });

    // Boundary: undefined data
    it('should return null when data is undefined', () => {
      const event: SSEEvent = {} as SSEEvent;
      const result = parseSSEData(event);

      expect(result).toBeNull();
    });

    // Path: nested JSON
    it('should parse nested JSON structures', () => {
      const event: SSEEvent = {
        data: '{"outer":{"inner":{"deep":"value"}}}',
      };
      const result = parseSSEData<{ outer: { inner: { deep: string } } }>(event);

      expect(result).toEqual({ outer: { inner: { deep: 'value' } } });
    });

    // Path: JSON array
    it('should parse JSON arrays', () => {
      const event: SSEEvent = { data: '[1,2,3]' };
      const result = parseSSEData<number[]>(event);

      expect(result).toEqual([1, 2, 3]);
    });

    // Path: JSON primitive
    it('should parse JSON primitives', () => {
      const event: SSEEvent = { data: '"just a string"' };
      const result = parseSSEData<string>(event);

      expect(result).toBe('just a string');
    });

    // Path: JSON null
    it('should parse JSON null', () => {
      const event: SSEEvent = { data: 'null' };
      const result = parseSSEData(event);

      expect(result).toBeNull();
    });
  });
});
