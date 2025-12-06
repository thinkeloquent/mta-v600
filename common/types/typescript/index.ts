/**
 * Common TypeScript types for MTA-v600.
 *
 * This module contains shared type definitions used across Fastify and frontend applications.
 */

/**
 * Standard API response wrapper
 */
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: ErrorDetail;
  meta?: ResponseMeta;
}

/**
 * Error detail structure
 */
export interface ErrorDetail {
  code: string;
  message: string;
  details?: unknown;
}

/**
 * Response metadata
 */
export interface ResponseMeta {
  timestamp?: string;
  requestId?: string;
  version?: string;
}

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/**
 * Hello endpoint response
 */
export interface HelloResponse {
  message: string;
  timestamp: string;
}

/**
 * Echo endpoint request/response
 */
export interface EchoPayload {
  [key: string]: unknown;
}
