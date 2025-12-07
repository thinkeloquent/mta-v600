/**
 * Tests for diagnostics.mts
 * Logic testing: Decision/Branch, State, Path coverage
 */
import diagnostics_channel from 'node:diagnostics_channel';
import {
  CHANNELS,
  emitRequestStart,
  emitRequestEnd,
  emitRequestError,
  onRequestStart,
  onRequestEnd,
  onRequestError,
  onAllEvents,
} from '../src/diagnostics.mjs';
import type { DiagnosticsEvent } from '../src/types.mjs';

describe('diagnostics', () => {
  beforeEach(() => {
    // Unsubscribe all listeners from channels
    for (const channelName of Object.values(CHANNELS)) {
      const channel = diagnostics_channel.channel(channelName);
      // Clear any existing subscribers by creating a new channel reference
      // Note: diagnostics_channel doesn't have a clear method, we handle this in tests
    }
  });

  describe('CHANNELS', () => {
    // Path: channel names defined
    it('should define REQUEST_START channel', () => {
      expect(CHANNELS.REQUEST_START).toBe('fetch-client:request:start');
    });

    it('should define REQUEST_END channel', () => {
      expect(CHANNELS.REQUEST_END).toBe('fetch-client:request:end');
    });

    it('should define REQUEST_ERROR channel', () => {
      expect(CHANNELS.REQUEST_ERROR).toBe('fetch-client:request:error');
    });

    it('should define STREAM_START channel', () => {
      expect(CHANNELS.STREAM_START).toBe('fetch-client:stream:start');
    });

    it('should define STREAM_END channel', () => {
      expect(CHANNELS.STREAM_END).toBe('fetch-client:stream:end');
    });

    it('should define STREAM_ERROR channel', () => {
      expect(CHANNELS.STREAM_ERROR).toBe('fetch-client:stream:error');
    });
  });

  describe('emitRequestStart', () => {
    // Decision: with subscribers
    it('should publish event when there are subscribers', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestStart((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com/users', { 'X-Custom': 'value' });

      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0].name).toBe('request:start');
      expect(receivedEvents[0].request?.method).toBe('GET');
      expect(receivedEvents[0].request?.url).toBe('https://api.example.com/users');
      expect(receivedEvents[0].request?.headers).toEqual({ 'X-Custom': 'value' });

      unsubscribe();
    });

    // Decision: no subscribers
    it('should not throw when there are no subscribers', () => {
      expect(() => {
        emitRequestStart('POST', 'https://api.example.com/data');
      }).not.toThrow();
    });

    // Path: includes timestamp
    it('should include timestamp in event', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const before = Date.now();
      const unsubscribe = onRequestStart((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com');

      const after = Date.now();

      expect(receivedEvents[0].timestamp).toBeGreaterThanOrEqual(before);
      expect(receivedEvents[0].timestamp).toBeLessThanOrEqual(after);

      unsubscribe();
    });

    // Path: without headers
    it('should work without headers', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestStart((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com');

      expect(receivedEvents[0].request?.headers).toBeUndefined();

      unsubscribe();
    });
  });

  describe('emitRequestEnd', () => {
    // Decision: with subscribers
    it('should publish event when there are subscribers', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestEnd((event) => receivedEvents.push(event));

      emitRequestEnd('GET', 'https://api.example.com', 200, 150, { 'content-type': 'application/json' });

      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0].name).toBe('request:end');
      expect(receivedEvents[0].duration).toBe(150);
      expect(receivedEvents[0].response?.status).toBe(200);
      expect(receivedEvents[0].response?.headers).toEqual({ 'content-type': 'application/json' });

      unsubscribe();
    });

    // Decision: no subscribers
    it('should not throw when there are no subscribers', () => {
      expect(() => {
        emitRequestEnd('GET', 'https://api.example.com', 200, 100);
      }).not.toThrow();
    });

    // Path: without headers
    it('should work without response headers', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestEnd((event) => receivedEvents.push(event));

      emitRequestEnd('POST', 'https://api.example.com', 201, 50);

      expect(receivedEvents[0].response?.headers).toBeUndefined();

      unsubscribe();
    });
  });

  describe('emitRequestError', () => {
    // Decision: with subscribers
    it('should publish event when there are subscribers', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestError((event) => receivedEvents.push(event));
      const error = new Error('Connection failed');

      emitRequestError('GET', 'https://api.example.com', error, 1000);

      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0].name).toBe('request:error');
      expect(receivedEvents[0].error).toBe(error);
      expect(receivedEvents[0].duration).toBe(1000);

      unsubscribe();
    });

    // Decision: no subscribers
    it('should not throw when there are no subscribers', () => {
      expect(() => {
        emitRequestError('GET', 'https://api.example.com', new Error('test'), 0);
      }).not.toThrow();
    });
  });

  describe('onRequestStart', () => {
    // Path: subscribe and receive events
    it('should receive events after subscribing', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestStart((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com');

      expect(receivedEvents).toHaveLength(1);

      unsubscribe();
    });

    // State: unsubscribe stops receiving
    it('should stop receiving events after unsubscribe', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestStart((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com');
      expect(receivedEvents).toHaveLength(1);

      unsubscribe();

      emitRequestStart('POST', 'https://api.example.com');
      expect(receivedEvents).toHaveLength(1); // Still 1, not 2
    });

    // Path: multiple subscribers
    it('should support multiple subscribers', () => {
      const events1: DiagnosticsEvent[] = [];
      const events2: DiagnosticsEvent[] = [];

      const unsubscribe1 = onRequestStart((event) => events1.push(event));
      const unsubscribe2 = onRequestStart((event) => events2.push(event));

      emitRequestStart('GET', 'https://api.example.com');

      expect(events1).toHaveLength(1);
      expect(events2).toHaveLength(1);

      unsubscribe1();
      unsubscribe2();
    });
  });

  describe('onRequestEnd', () => {
    // Path: subscribe and receive events
    it('should receive events after subscribing', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestEnd((event) => receivedEvents.push(event));

      emitRequestEnd('GET', 'https://api.example.com', 200, 100);

      expect(receivedEvents).toHaveLength(1);

      unsubscribe();
    });

    // State: unsubscribe stops receiving
    it('should stop receiving events after unsubscribe', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestEnd((event) => receivedEvents.push(event));

      emitRequestEnd('GET', 'https://api.example.com', 200, 100);
      unsubscribe();
      emitRequestEnd('POST', 'https://api.example.com', 201, 50);

      expect(receivedEvents).toHaveLength(1);
    });
  });

  describe('onRequestError', () => {
    // Path: subscribe and receive events
    it('should receive events after subscribing', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestError((event) => receivedEvents.push(event));

      emitRequestError('GET', 'https://api.example.com', new Error('test'), 100);

      expect(receivedEvents).toHaveLength(1);

      unsubscribe();
    });

    // State: unsubscribe stops receiving
    it('should stop receiving events after unsubscribe', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onRequestError((event) => receivedEvents.push(event));

      emitRequestError('GET', 'https://api.example.com', new Error('test'), 100);
      unsubscribe();
      emitRequestError('POST', 'https://api.example.com', new Error('test2'), 50);

      expect(receivedEvents).toHaveLength(1);
    });
  });

  describe('onAllEvents', () => {
    // Path: subscribes to all three channels
    it('should receive events from all channels', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onAllEvents((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com');
      emitRequestEnd('GET', 'https://api.example.com', 200, 100);
      emitRequestError('POST', 'https://api.example.com', new Error('test'), 50);

      expect(receivedEvents).toHaveLength(3);
      expect(receivedEvents[0].name).toBe('request:start');
      expect(receivedEvents[1].name).toBe('request:end');
      expect(receivedEvents[2].name).toBe('request:error');

      unsubscribe();
    });

    // State: unsubscribe cleanup
    it('should unsubscribe from all channels', () => {
      const receivedEvents: DiagnosticsEvent[] = [];
      const unsubscribe = onAllEvents((event) => receivedEvents.push(event));

      emitRequestStart('GET', 'https://api.example.com');
      expect(receivedEvents).toHaveLength(1);

      unsubscribe();

      emitRequestStart('POST', 'https://api.example.com');
      emitRequestEnd('GET', 'https://api.example.com', 200, 100);
      emitRequestError('GET', 'https://api.example.com', new Error('test'), 50);

      expect(receivedEvents).toHaveLength(1); // Still 1, no new events
    });

    // Path: same handler for all events
    it('should use the same handler for all event types', () => {
      const handler = jest.fn();
      const unsubscribe = onAllEvents(handler);

      emitRequestStart('GET', 'https://api.example.com');
      emitRequestEnd('GET', 'https://api.example.com', 200, 100);

      expect(handler).toHaveBeenCalledTimes(2);

      unsubscribe();
    });
  });
});
