import { BaseApiToken } from './base.mjs';

/**
 * {{APP_NAME_TITLE}} API Token provider.
 */
export class {{ APP_NAME_PASCAL }}ApiToken extends BaseApiToken {
    /**
     * Get the environment variable name for the API key.
     */
    _getEnvApiKeyName() {
        return '{{APP_NAME_UPPER_SNAKE}}_TOKEN';
    }

    /**
     * Get the provider configuration.
     */
    _getProviderConfig() {
        return this.configStore.getProvider('{{APP_NAME_SHORT}}');
    }
}
