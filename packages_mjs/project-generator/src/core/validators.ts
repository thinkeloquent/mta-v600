/**
 * Validation utilities for project names and inputs.
 */

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validate that a project name is in kebab-case format.
 * Rules:
 * - Must start with a lowercase letter
 * - Can contain lowercase letters, numbers, and hyphens
 * - Must not have consecutive hyphens
 * - Must not end with a hyphen
 */
export function validateKebabCase(name: string): ValidationResult {
  if (!name || name.trim() === '') {
    return { valid: false, error: 'Project name is required' };
  }

  // Single character name (just a letter)
  if (/^[a-z]$/.test(name)) {
    return { valid: true };
  }

  // General kebab-case pattern
  if (!/^[a-z][a-z0-9-]*[a-z0-9]$/.test(name)) {
    return {
      valid: false,
      error: 'Project name must be kebab-case (lowercase letters, numbers, and hyphens, starting with a letter)',
    };
  }

  if (name.includes('--')) {
    return { valid: false, error: 'Project name cannot contain consecutive hyphens' };
  }

  return { valid: true };
}

/**
 * Validate project name for use in the CLI.
 * Returns true if valid, or an error string if invalid.
 * Compatible with @clack/prompts validate function signature.
 */
export function validateProjectName(name: string): string | void {
  const result = validateKebabCase(name);
  if (!result.valid) {
    return result.error;
  }
}

/**
 * Validate that a directory path does not already exist.
 */
export async function validatePathDoesNotExist(
  path: string,
  fs: { pathExists: (p: string) => Promise<boolean> }
): Promise<ValidationResult> {
  const exists = await fs.pathExists(path);
  if (exists) {
    return { valid: false, error: `Directory already exists: ${path}` };
  }
  return { valid: true };
}

/**
 * Reserved names that cannot be used as project names.
 */
export const RESERVED_NAMES = new Set([
  'node_modules',
  'dist',
  'build',
  'src',
  'test',
  'tests',
  'lib',
  'bin',
  'public',
  'private',
  'static',
  'assets',
  'config',
  'scripts',
]);

/**
 * Validate that a name is not reserved.
 */
export function validateNotReserved(name: string): ValidationResult {
  if (RESERVED_NAMES.has(name)) {
    return { valid: false, error: `"${name}" is a reserved name and cannot be used` };
  }
  return { valid: true };
}

/**
 * Combined validation for project names.
 */
export function validateFullProjectName(name: string): ValidationResult {
  // Check kebab-case
  const kebabResult = validateKebabCase(name);
  if (!kebabResult.valid) {
    return kebabResult;
  }

  // Check reserved names
  const reservedResult = validateNotReserved(name);
  if (!reservedResult.valid) {
    return reservedResult;
  }

  return { valid: true };
}
