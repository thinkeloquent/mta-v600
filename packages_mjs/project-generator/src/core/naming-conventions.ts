/**
 * Naming convention utilities for project generation.
 * Converts kebab-case names to various naming conventions.
 */

/**
 * Convert kebab-case to PascalCase.
 * @example toPascalCase('user-service') => 'UserService'
 */
export function toPascalCase(str: string): string {
  return str
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join('');
}

/**
 * Convert kebab-case to camelCase.
 * @example toCamelCase('user-service') => 'userService'
 */
export function toCamelCase(str: string): string {
  const pascal = toPascalCase(str);
  return pascal.charAt(0).toLowerCase() + pascal.slice(1);
}

/**
 * Convert kebab-case to snake_case.
 * @example toSnakeCase('user-service') => 'user_service'
 */
export function toSnakeCase(str: string): string {
  return str.replace(/-/g, '_');
}

/**
 * Convert kebab-case to Title Case.
 * @example toTitleCase('user-service') => 'User Service'
 */
export function toTitleCase(str: string): string {
  return str
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Convert kebab-case to UPPER_SNAKE_CASE.
 * @example toUpperSnakeCase('user-service') => 'USER_SERVICE'
 */
export function toUpperSnakeCase(str: string): string {
  return str.replace(/-/g, '_').toUpperCase();
}

/**
 * Remove 'app-' prefix from name if present.
 * @example toShortName('app-user-service') => 'user-service'
 */
export function toShortName(str: string): string {
  return str.startsWith('app-') ? str.slice(4) : str;
}

/**
 * Placeholder tokens used in templates.
 */
export const PLACEHOLDERS = {
  APP_NAME: '{{APP_NAME}}',
  APP_NAME_SHORT: '{{APP_NAME_SHORT}}',
  APP_NAME_PASCAL: '{{APP_NAME_PASCAL}}',
  APP_NAME_CAMEL: '{{APP_NAME_CAMEL}}',
  APP_NAME_SNAKE: '{{APP_NAME_SNAKE}}',
  APP_NAME_TITLE: '{{APP_NAME_TITLE}}',
  APP_NAME_UPPER_SNAKE: '{{APP_NAME_UPPER_SNAKE}}',
} as const;

/**
 * Generate all naming convention variants for a given app name.
 */
export function generateNameVariants(appName: string): Record<string, string> {
  return {
    name: appName,
    short: toShortName(appName),
    pascal: toPascalCase(appName),
    camel: toCamelCase(appName),
    snake: toSnakeCase(appName),
    title: toTitleCase(appName),
    upperSnake: toUpperSnakeCase(appName),
  };
}

/**
 * Replace all placeholders in a string with actual values.
 */
export function replacePlaceholders(content: string, appName: string): string {
  const shortName = toShortName(appName);
  return content
    .replace(new RegExp(PLACEHOLDERS.APP_NAME_SHORT, 'g'), shortName)
    .replace(new RegExp(PLACEHOLDERS.APP_NAME_PASCAL, 'g'), toPascalCase(appName))
    .replace(new RegExp(PLACEHOLDERS.APP_NAME_CAMEL, 'g'), toCamelCase(appName))
    .replace(new RegExp(PLACEHOLDERS.APP_NAME_SNAKE, 'g'), toSnakeCase(appName))
    .replace(new RegExp(PLACEHOLDERS.APP_NAME_TITLE, 'g'), toTitleCase(appName))
    .replace(new RegExp(PLACEHOLDERS.APP_NAME_UPPER_SNAKE, 'g'), toUpperSnakeCase(appName))
    .replace(new RegExp(PLACEHOLDERS.APP_NAME, 'g'), appName);
}
