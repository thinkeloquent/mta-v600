/**
 * API token getters for external providers.
 */
export { BaseApiToken, ApiKeyResult, RequestContext } from './base.mjs';
export { AuthHeaderFactory, AuthHeader, AUTH_SCHEMES, CONFIG_AUTH_TYPE_MAP } from './auth_header_factory.mjs';
export { FigmaApiToken } from './figma.mjs';
export { GithubApiToken } from './github.mjs';
export { JiraApiToken } from './jira.mjs';
export { ConfluenceApiToken } from './confluence.mjs';
export { GeminiApiToken } from './gemini.mjs';
export { GeminiOpenAIApiToken } from './gemini_openai.mjs';
export { OpenAIApiToken } from './openai.mjs';
export { PostgresApiToken } from './postgres.mjs';
export { RedisApiToken } from './redis.mjs';
export { RallyApiToken } from './rally.mjs';
export { ElasticsearchApiToken } from './elasticsearch.mjs';
export { SaucelabsApiToken } from './saucelabs.mjs';
export { SonarApiToken } from './sonar.mjs';
export { AkamaiApiToken } from './akamai.mjs';
export { ServicenowApiToken } from './servicenow.mjs';
export { StatsigApiToken } from './statsig.mjs';

import { FigmaApiToken } from './figma.mjs';
import { GithubApiToken } from './github.mjs';
import { JiraApiToken } from './jira.mjs';
import { ConfluenceApiToken } from './confluence.mjs';
import { GeminiApiToken } from './gemini.mjs';
import { GeminiOpenAIApiToken } from './gemini_openai.mjs';
import { OpenAIApiToken } from './openai.mjs';
import { PostgresApiToken } from './postgres.mjs';
import { RedisApiToken } from './redis.mjs';
import { RallyApiToken } from './rally.mjs';
import { ElasticsearchApiToken } from './elasticsearch.mjs';
import { SaucelabsApiToken } from './saucelabs.mjs';
import { SonarApiToken } from './sonar.mjs';
import { AkamaiApiToken } from './akamai.mjs';
import { ServicenowApiToken } from './servicenow.mjs';
import { StatsigApiToken } from './statsig.mjs';

/**
 * Registry mapping provider names to their token classes.
 */
export const PROVIDER_REGISTRY = {
  figma: FigmaApiToken,
  github: GithubApiToken,
  jira: JiraApiToken,
  confluence: ConfluenceApiToken,
  gemini: GeminiApiToken,
  gemini_openai: GeminiOpenAIApiToken,
  openai: OpenAIApiToken,
  postgres: PostgresApiToken,
  redis: RedisApiToken,
  rally: RallyApiToken,
  elasticsearch: ElasticsearchApiToken,
  saucelabs: SaucelabsApiToken,
  sonar: SonarApiToken,
  sonarqube: SonarApiToken,
  sonarcloud: SonarApiToken,
  akamai: AkamaiApiToken,
  servicenow: ServicenowApiToken,
  statsig: StatsigApiToken,
};

/**
 * Get the API token class for a provider name.
 * @param {string} providerName
 * @returns {typeof BaseApiToken | undefined}
 */
export function getApiTokenClass(providerName) {
  return PROVIDER_REGISTRY[providerName.toLowerCase()];
}
