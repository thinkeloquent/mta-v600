from pydantic import SecretStr
import pytest
import base64
from fetch_auth_config import AuthType, AuthConfig, resolve_auth_headers

class TestAuthConfig:
    
    def test_basic_auth_integration(self):
        username = "user"
        password = "password123"
        config = AuthConfig(
            type=AuthType.BASIC,
            username=username,
            password=SecretStr(password)
        )
        headers = resolve_auth_headers(config)
        
        expected_credentials = f"{username}:{password}"
        expected_b64 = base64.b64encode(expected_credentials.encode()).decode()
        
        assert headers == {"Authorization": f"Basic {expected_b64}"}

    def test_basic_email_token_integration(self):
        email = "test@example.com"
        token = "tok123"
        config = AuthConfig(
            type=AuthType.BASIC_EMAIL_TOKEN,
            email=email,
            token=SecretStr(token)
        )
        headers = resolve_auth_headers(config)
        expected_b64 = base64.b64encode(f"{email}:{token}".encode()).decode()
        assert headers == {"Authorization": f"Basic {expected_b64}"}

    def test_bearer_auth_integration(self):
        token = "test-token-123"
        config = AuthConfig(
            type=AuthType.BEARER,
            token=SecretStr(token)
        )
        headers = resolve_auth_headers(config)
        assert headers == {"Authorization": f"Bearer {token}"}
        
    def test_bearer_email_password_integration(self):
        email = "e"
        password = "p"
        config = AuthConfig(
            type=AuthType.BEARER_EMAIL_PASSWORD,
            email=email,
            password=SecretStr(password)
        )
        headers = resolve_auth_headers(config)
        expected_b64 = base64.b64encode(f"{email}:{password}".encode()).decode()
        assert headers == {"Authorization": f"Bearer {expected_b64}"}

    def test_custom_auth_integration(self):
        config = AuthConfig(
            type=AuthType.CUSTOM_HEADER,
            header_key="X-API-Key",
            header_value=SecretStr("my-api-key")
        )
        headers = resolve_auth_headers(config)
        assert headers == {"X-API-Key": "my-api-key"}
        
    def test_none_auth(self):
        config = AuthConfig(type=AuthType.NONE)
        headers = resolve_auth_headers(config)
        assert headers == {}
