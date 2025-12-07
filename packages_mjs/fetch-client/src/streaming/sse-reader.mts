/**
 * Server-Sent Events (SSE) stream parser
 */
import type { Readable } from 'node:stream';
import type { SSEEvent } from '../types.mjs';

/**
 * Parse SSE stream from a readable body
 *
 * @param body - Readable stream (undici body)
 * @yields SSEEvent objects
 */
export async function* parseSSEStream(
  body: Readable | AsyncIterable<Uint8Array>
): AsyncGenerator<SSEEvent, void, unknown> {
  const decoder = new TextDecoder();
  let buffer = '';

  for await (const chunk of body) {
    buffer += decoder.decode(chunk, { stream: true });

    // Split on double newlines (SSE event delimiter)
    const parts = buffer.split('\n\n');

    // Keep the last part in buffer (may be incomplete)
    buffer = parts.pop() || '';

    for (const part of parts) {
      const event = parseSSEEvent(part);
      if (event) {
        yield event;
      }
    }
  }

  // Handle any remaining data
  if (buffer.trim()) {
    const event = parseSSEEvent(buffer);
    if (event) {
      yield event;
    }
  }
}

/**
 * Parse a single SSE event from text
 *
 * @param text - Raw SSE event text
 * @returns Parsed SSEEvent or null if invalid
 */
export function parseSSEEvent(text: string): SSEEvent | null {
  const lines = text.split('\n');
  const event: SSEEvent = { data: '' };
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith(':')) {
      // Comment line, ignore
      continue;
    }

    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) {
      // Field with no value
      continue;
    }

    const field = line.slice(0, colonIndex);
    // Value starts after colon, strip leading space if present
    let value = line.slice(colonIndex + 1);
    if (value.startsWith(' ')) {
      value = value.slice(1);
    }

    switch (field) {
      case 'event':
        event.event = value;
        break;
      case 'id':
        event.id = value;
        break;
      case 'retry':
        event.retry = parseInt(value, 10);
        break;
      case 'data':
        dataLines.push(value);
        break;
    }
  }

  // Join data lines with newlines
  event.data = dataLines.join('\n');

  // Return null if no data
  if (!event.data && !event.event) {
    return null;
  }

  return event;
}

/**
 * Parse SSE data field as JSON
 *
 * @param event - SSE event
 * @returns Parsed JSON data or null if parsing fails
 */
export function parseSSEData<T = unknown>(event: SSEEvent): T | null {
  if (!event.data) {
    return null;
  }

  // Handle [DONE] marker (common in OpenAI-style streams)
  if (event.data.trim() === '[DONE]') {
    return null;
  }

  try {
    return JSON.parse(event.data) as T;
  } catch {
    return null;
  }
}
