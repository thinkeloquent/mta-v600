/**
 * Newline-Delimited JSON (NDJSON) stream parser
 */
import type { Readable } from 'node:stream';
import type { Serializer } from '../types.mjs';

/**
 * Parse NDJSON stream from a readable body
 *
 * @param body - Readable stream (undici body)
 * @param serializer - JSON serializer/deserializer
 * @yields Parsed JSON objects
 */
export async function* parseNdjsonStream<T = unknown>(
  body: Readable | AsyncIterable<Uint8Array>,
  serializer: Serializer
): AsyncGenerator<T, void, unknown> {
  const decoder = new TextDecoder();
  let buffer = '';

  for await (const chunk of body) {
    buffer += decoder.decode(chunk, { stream: true });

    // Split on newlines
    const lines = buffer.split('\n');

    // Keep the last line in buffer (may be incomplete)
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }

      try {
        const parsed = serializer.deserialize<T>(trimmed);
        yield parsed;
      } catch (error) {
        // Skip malformed lines
        console.warn('Failed to parse NDJSON line:', error);
      }
    }
  }

  // Handle any remaining data
  const trimmed = buffer.trim();
  if (trimmed) {
    try {
      const parsed = serializer.deserialize<T>(trimmed);
      yield parsed;
    } catch {
      // Skip malformed final line
    }
  }
}

/**
 * Simple NDJSON parser using default JSON.parse
 *
 * @param body - Readable stream
 * @yields Parsed JSON objects
 */
export async function* parseNdjsonStreamSimple<T = unknown>(
  body: Readable | AsyncIterable<Uint8Array>
): AsyncGenerator<T, void, unknown> {
  const defaultSerializer: Serializer = {
    serialize: JSON.stringify,
    deserialize: JSON.parse,
  };

  yield* parseNdjsonStream<T>(body, defaultSerializer);
}

/**
 * Encode objects as NDJSON
 *
 * @param items - Items to encode
 * @param serializer - JSON serializer
 * @returns NDJSON string
 */
export function encodeNdjson(
  items: unknown[],
  serializer: Serializer = { serialize: JSON.stringify, deserialize: JSON.parse }
): string {
  return items.map((item) => serializer.serialize(item)).join('\n');
}
