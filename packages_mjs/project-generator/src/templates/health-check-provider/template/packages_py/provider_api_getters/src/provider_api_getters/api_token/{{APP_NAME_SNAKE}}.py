from .base import BaseApiToken

class {{APP_NAME_PASCAL}}ApiToken(BaseApiToken):
    """
    {{APP_NAME_TITLE}} API Token provider.

    Expected Configuration:
    - base_url: The API base URL
    - env_api_key: Name of environment variable for token
    """

    def _get_env_api_key_name(self) -> str:
        return "{{APP_NAME_UPPER_SNAKE}}_TOKEN"

    def _get_provider_config(self) -> dict:
        return self.config_store.get_provider("{{APP_NAME_SHORT}}")
