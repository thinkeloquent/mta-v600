/**
 * Per-provider health check modules.
 *
 * Each module is a standalone script that can be run directly for debugging:
 *   node confluence_health_check.mjs
 *   node github_health_check.mjs
 *   etc.
 *
 * These modules directly use:
 * - static_config for YAML configuration
 * - provider_api_getters for API token resolution
 * - fetch_client for HTTP requests with proxy/auth support
 */

export { checkConfluenceHealth } from './confluence_health_check.mjs';
export { checkJiraHealth } from './jira_health_check.mjs';
export { checkGithubHealth } from './github_health_check.mjs';
export { checkFigmaHealth } from './figma_health_check.mjs';
export { checkGeminiOpenaiHealth } from './gemini_openai_health_check.mjs';
export { checkRallyHealth } from './rally_health_check.mjs';
export { checkSaucelabsHealth } from './saucelabs_health_check.mjs';
export { checkSonarHealth } from './sonar_health_check.mjs';
export { checkAkamaiHealth } from './akamai_health_check.mjs';
export { checkPostgresHealth } from './postgres_health_check.mjs';
export { checkRedisHealth } from './redis_health_check.mjs';
export { checkElasticsearchHealth } from './elasticsearch_health_check.mjs';
