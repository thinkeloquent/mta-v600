/**
 * Tests for console-print printer module.
 */

import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';

import {
  hasColors,
  printSection,
  printRule,
  printJson,
  maskSensitive,
  maskUrl,
  printInfo,
  printSuccess,
  printWarning,
  printError,
  printDebug,
  printTable,
  printPanel,
  printKeyValue,
  printKeyValues,
} from '../src/printer.mjs';

describe('console-print', () => {
  // Capture console.log output
  let consoleSpy;

  beforeEach(() => {
    consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  describe('hasColors', () => {
    it('should return a boolean', () => {
      expect(typeof hasColors()).toBe('boolean');
    });
  });

  describe('maskSensitive', () => {
    it('should return placeholder for null/undefined', () => {
      expect(maskSensitive(null)).toBe('<none>');
      expect(maskSensitive(undefined)).toBe('<none>');
      expect(maskSensitive('')).toBe('<none>');
    });

    it('should mask short values completely', () => {
      expect(maskSensitive('abc')).toBe('***');
      expect(maskSensitive('abcd')).toBe('****');
    });

    it('should show first N characters for longer values', () => {
      expect(maskSensitive('password123')).toBe('pass***');
      expect(maskSensitive('secrettoken')).toBe('secr***');
    });

    it('should respect showChars option', () => {
      expect(maskSensitive('password123', { showChars: 2 })).toBe('pa***');
      expect(maskSensitive('password123', { showChars: 6 })).toBe('passwo***');
    });

    it('should respect placeholder option', () => {
      expect(maskSensitive(null, { placeholder: 'N/A' })).toBe('N/A');
    });
  });

  describe('maskUrl', () => {
    it('should return placeholder for null/undefined', () => {
      expect(maskUrl(null)).toBe('<none>');
      expect(maskUrl(undefined)).toBe('<none>');
      expect(maskUrl('')).toBe('<none>');
    });

    it('should mask password in URL', () => {
      const url = 'redis://user:secretpassword@localhost:6379/0';
      const masked = maskUrl(url);
      expect(masked).toContain('****');
      expect(masked).not.toContain('secretpassword');
    });

    it('should mask sensitive query parameters', () => {
      const url = 'https://api.example.com?key=myapikey&other=value';
      const masked = maskUrl(url);
      expect(masked).toContain('key=****');
      expect(masked).toContain('other=value');
    });

    it('should handle invalid URLs gracefully', () => {
      const invalid = 'not-a-valid-url://host:password@server';
      // Should not throw
      expect(() => maskUrl(invalid)).not.toThrow();
    });
  });

  describe('printSection', () => {
    it('should print section header', () => {
      printSection('Test Section');

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('=');
      expect(output).toContain('Test Section');
    });
  });

  describe('printRule', () => {
    it('should print horizontal rule', () => {
      printRule();

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls[0][0];
      expect(output).toMatch(/^-+$/);
    });

    it('should print rule with title', () => {
      printRule('Title');

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls[0][0];
      expect(output).toContain('Title');
    });
  });

  describe('printJson', () => {
    it('should print JSON object', () => {
      printJson({ key: 'value' });

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls[0][0];
      expect(output).toContain('key');
      expect(output).toContain('value');
    });

    it('should print JSON string', () => {
      printJson('{"key": "value"}');

      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should handle arrays', () => {
      printJson([1, 2, 3]);

      expect(consoleSpy).toHaveBeenCalled();
    });

    it('should print title when provided as string', () => {
      printJson({ key: 'value' }, 'My Title');

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('My Title');
    });

    it('should print title when provided in options object', () => {
      printJson({ key: 'value' }, { title: 'Config Data' });

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('Config Data');
    });
  });

  describe('status messages', () => {
    it('should print info message', () => {
      printInfo('Info message');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('INFO');
    });

    it('should print info message with title string', () => {
      printInfo('Info message', 'Redis');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('INFO:Redis');
    });

    it('should print info message with title in options', () => {
      printInfo('Info message', { title: 'Config' });
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('INFO:Config');
    });

    it('should print success message', () => {
      printSuccess('Success message');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('OK');
    });

    it('should print success message with title', () => {
      printSuccess('Connected', 'Redis');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('OK:Redis');
    });

    it('should print warning message', () => {
      printWarning('Warning message');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('WARN');
    });

    it('should print warning message with title', () => {
      printWarning('Slow response', 'API');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('WARN:API');
    });

    it('should print error message', () => {
      printError('Error message');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('ERROR');
    });

    it('should print error message with title', () => {
      printError('Connection failed', 'Database');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('ERROR:Database');
    });

    it('should print debug message', () => {
      printDebug('Debug message');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('DEBUG');
    });

    it('should print debug message with title', () => {
      printDebug('Inspecting config', 'Auth');
      expect(consoleSpy).toHaveBeenCalled();
      expect(consoleSpy.mock.calls[0][0]).toContain('DEBUG:Auth');
    });
  });

  describe('printTable', () => {
    it('should handle empty data', () => {
      printTable([]);
      expect(consoleSpy).toHaveBeenCalledWith('(empty table)');
    });

    it('should print table with data', () => {
      printTable([
        { name: 'Alice', age: 30 },
        { name: 'Bob', age: 25 },
      ]);

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('name');
      expect(output).toContain('Alice');
      expect(output).toContain('Bob');
    });

    it('should print table with title', () => {
      printTable([{ a: 1 }], { title: 'My Table' });

      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('My Table');
    });
  });

  describe('printPanel', () => {
    it('should print content in panel', () => {
      printPanel('Content here');

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('+');
      expect(output).toContain('Content here');
    });

    it('should print panel with title', () => {
      printPanel('Content', { title: 'Panel Title' });

      const output = consoleSpy.mock.calls.map((c) => c[0]).join('\n');
      expect(output).toContain('Panel Title');
    });
  });

  describe('printKeyValue', () => {
    it('should print key-value pair', () => {
      printKeyValue('Host', 'localhost');

      expect(consoleSpy).toHaveBeenCalled();
      const output = consoleSpy.mock.calls[0][0];
      expect(output).toContain('Host');
      expect(output).toContain('localhost');
    });
  });

  describe('printKeyValues', () => {
    it('should print multiple key-value pairs', () => {
      printKeyValues({ host: 'localhost', port: 6379 });

      expect(consoleSpy).toHaveBeenCalledTimes(2);
    });
  });
});
