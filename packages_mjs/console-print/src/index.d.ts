/**
 * Type declarations for @internal/console-print
 */

/**
 * Check if colors are available.
 */
export function hasColors(): boolean;

/**
 * Print a section header with a title.
 */
export function printSection(title: string, options?: { width?: number; char?: string }): void;

/**
 * Print a horizontal rule.
 */
export function printRule(title?: string, options?: { width?: number; char?: string }): void;

/**
 * Print JSON data with indentation.
 */
export function printJson(data: unknown, optionsOrTitle?: string | { title?: string; indent?: number }): void;

/**
 * Mask sensitive values for logging.
 */
export function maskSensitive(value: string | null | undefined, options?: { showChars?: number; maskChar?: string; placeholder?: string }): string;

/**
 * Mask Authorization header value for logging.
 * Shows first N characters (default: 15) to allow inspection of auth scheme prefix and partial token.
 */
export function maskAuthHeader(value: string | null | undefined, visibleChars?: number): string;

/**
 * Mask a URL by hiding password and sensitive query parameters.
 */
export function maskUrl(url: string | null | undefined): string;

/**
 * Print an info message.
 */
export function printInfo(message: string, optionsOrTitle?: string | { title?: string }): void;

/**
 * Print a success message.
 */
export function printSuccess(message: string, optionsOrTitle?: string | { title?: string }): void;

/**
 * Print a warning message.
 */
export function printWarning(message: string, optionsOrTitle?: string | { title?: string }): void;

/**
 * Print an error message.
 */
export function printError(message: string, optionsOrTitle?: string | { title?: string }): void;

/**
 * Print a debug message.
 */
export function printDebug(message: string, optionsOrTitle?: string | { title?: string }): void;

/**
 * Print data as a simple table.
 */
export function printTable(data: Array<Record<string, unknown>>, options?: { title?: string; columns?: string[] }): void;

/**
 * Print content in a simple box/panel.
 */
export function printPanel(content: string, options?: { title?: string; width?: number }): void;

/**
 * Print a labeled value (key: value format).
 */
export function printKeyValue(label: string, value: unknown, options?: { indent?: number }): void;

/**
 * Print multiple key-value pairs from an object.
 */
export function printKeyValues(obj: Record<string, unknown>, options?: { indent?: number }): void;

/**
 * Package version.
 */
export const VERSION: string;
