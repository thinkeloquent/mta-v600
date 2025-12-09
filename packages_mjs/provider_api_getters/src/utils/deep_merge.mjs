/**
 * Deep merge utility for provider configuration overrides.
 *
 * Recursively merges source object into target object. Source values
 * override target values, with nested objects being merged recursively.
 */

/**
 * Deep merge two objects recursively.
 *
 * @param {Object} target - The base object to merge into
 * @param {Object} source - The object with override values
 * @returns {Object} A new merged object
 *
 * @example
 * const global = { proxy: { cert_verify: true, proxy_urls: { dev: 'http://dev:8080' } } };
 * const provider = { proxy: { cert_verify: false } };
 * const merged = deepMerge(global, provider);
 * // { proxy: { cert_verify: false, proxy_urls: { dev: 'http://dev:8080' } } }
 */
export function deepMerge(target, source) {
  // Handle null/undefined
  if (source === null || source === undefined) {
    return target;
  }
  if (target === null || target === undefined) {
    return source;
  }

  // If source is not an object, return source (override)
  if (typeof source !== 'object' || Array.isArray(source)) {
    return source;
  }

  // If target is not an object, return source
  if (typeof target !== 'object' || Array.isArray(target)) {
    return source;
  }

  // Both are objects, merge recursively
  const result = { ...target };

  for (const key of Object.keys(source)) {
    const sourceValue = source[key];
    const targetValue = result[key];

    // Skip undefined values in source (don't override with undefined)
    if (sourceValue === undefined) {
      continue;
    }

    // Recursively merge nested objects
    if (
      sourceValue !== null &&
      typeof sourceValue === 'object' &&
      !Array.isArray(sourceValue) &&
      targetValue !== null &&
      typeof targetValue === 'object' &&
      !Array.isArray(targetValue)
    ) {
      result[key] = deepMerge(targetValue, sourceValue);
    } else {
      // Override with source value
      result[key] = sourceValue;
    }
  }

  return result;
}

export default deepMerge;
