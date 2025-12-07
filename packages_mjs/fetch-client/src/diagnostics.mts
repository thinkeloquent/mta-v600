/**
 * Diagnostics and observability for @internal/fetch-client
 *
 * Uses Node.js diagnostics_channel for emitting metrics and events.
 */
import diagnostics_channel from 'node:diagnostics_channel';
import type { DiagnosticsEvent, HttpMethod } from './types.mjs';

/**
 * Channel names
 */
export const CHANNELS = {
  REQUEST_START: 'fetch-client:request:start',
  REQUEST_END: 'fetch-client:request:end',
  REQUEST_ERROR: 'fetch-client:request:error',
  STREAM_START: 'fetch-client:stream:start',
  STREAM_END: 'fetch-client:stream:end',
  STREAM_ERROR: 'fetch-client:stream:error',
} as const;

/**
 * Get or create a diagnostics channel
 */
function getChannel(name: string): diagnostics_channel.Channel {
  return diagnostics_channel.channel(name);
}

/**
 * Emit request start event
 */
export function emitRequestStart(
  method: HttpMethod,
  url: string,
  headers?: Record<string, string>
): void {
  const channel = getChannel(CHANNELS.REQUEST_START);
  if (channel.hasSubscribers) {
    const event: DiagnosticsEvent = {
      name: 'request:start',
      timestamp: Date.now(),
      request: { method, url, headers },
    };
    channel.publish(event);
  }
}

/**
 * Emit request end event
 */
export function emitRequestEnd(
  method: HttpMethod,
  url: string,
  status: number,
  duration: number,
  headers?: Record<string, string>
): void {
  const channel = getChannel(CHANNELS.REQUEST_END);
  if (channel.hasSubscribers) {
    const event: DiagnosticsEvent = {
      name: 'request:end',
      timestamp: Date.now(),
      duration,
      request: { method, url },
      response: { status, headers },
    };
    channel.publish(event);
  }
}

/**
 * Emit request error event
 */
export function emitRequestError(
  method: HttpMethod,
  url: string,
  error: Error,
  duration: number
): void {
  const channel = getChannel(CHANNELS.REQUEST_ERROR);
  if (channel.hasSubscribers) {
    const event: DiagnosticsEvent = {
      name: 'request:error',
      timestamp: Date.now(),
      duration,
      request: { method, url },
      error,
    };
    channel.publish(event);
  }
}

/**
 * Subscribe to request start events
 */
export function onRequestStart(
  handler: (event: DiagnosticsEvent) => void
): () => void {
  const channel = getChannel(CHANNELS.REQUEST_START);
  channel.subscribe(handler as (message: unknown) => void);
  return () => channel.unsubscribe(handler as (message: unknown) => void);
}

/**
 * Subscribe to request end events
 */
export function onRequestEnd(
  handler: (event: DiagnosticsEvent) => void
): () => void {
  const channel = getChannel(CHANNELS.REQUEST_END);
  channel.subscribe(handler as (message: unknown) => void);
  return () => channel.unsubscribe(handler as (message: unknown) => void);
}

/**
 * Subscribe to request error events
 */
export function onRequestError(
  handler: (event: DiagnosticsEvent) => void
): () => void {
  const channel = getChannel(CHANNELS.REQUEST_ERROR);
  channel.subscribe(handler as (message: unknown) => void);
  return () => channel.unsubscribe(handler as (message: unknown) => void);
}

/**
 * Subscribe to all events
 */
export function onAllEvents(
  handler: (event: DiagnosticsEvent) => void
): () => void {
  const unsubscribes = [
    onRequestStart(handler),
    onRequestEnd(handler),
    onRequestError(handler),
  ];

  return () => {
    for (const unsubscribe of unsubscribes) {
      unsubscribe();
    }
  };
}
