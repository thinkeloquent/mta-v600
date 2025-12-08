/**
 * API token getters for external providers.
 */
export { BaseApiToken, ApiKeyResult, RequestContext } from './base.mjs';
export { FigmaApiToken } from './figma.mjs';
export { GithubApiToken } from './github.mjs';
export { JiraApiToken } from './jira.mjs';
export { ConfluenceApiToken } from './confluence.mjs';
export { GeminiOpenAIApiToken } from './gemini_openai.mjs';
export { PostgresApiToken } from './postgres.mjs';
export { RedisApiToken } from './redis.mjs';
export { RallyApiToken } from './rally.mjs';
export { ElasticsearchApiToken } from './elasticsearch.mjs';

import { FigmaApiToken } from './figma.mjs';
import { GithubApiToken } from './github.mjs';
import { JiraApiToken } from './jira.mjs';
import { ConfluenceApiToken } from './confluence.mjs';
import { GeminiOpenAIApiToken } from './gemini_openai.mjs';
import { PostgresApiToken } from './postgres.mjs';
import { RedisApiToken } from './redis.mjs';
import { RallyApiToken } from './rally.mjs';
import { ElasticsearchApiToken } from './elasticsearch.mjs';

/**
 * Registry mapping provider names to their token classes.
 */
export const PROVIDER_REGISTRY = {
  figma: FigmaApiToken,
  github: GithubApiToken,
  jira: JiraApiToken,
  confluence: ConfluenceApiToken,
  gemini: GeminiOpenAIApiToken,
  gemini_openai: GeminiOpenAIApiToken,
  openai: GeminiOpenAIApiToken,
  postgres: PostgresApiToken,
  redis: RedisApiToken,
  rally: RallyApiToken,
  elasticsearch: ElasticsearchApiToken,
};

/**
 * Get the API token class for a provider name.
 * @param {string} providerName
 * @returns {typeof BaseApiToken | undefined}
 */
export function getApiTokenClass(providerName) {
  return PROVIDER_REGISTRY[providerName.toLowerCase()];
}
