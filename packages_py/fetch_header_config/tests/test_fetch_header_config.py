import pytest
from pydantic import SecretStr
from fetch_header_config import HeaderConfig
from fetch_auth_config import AuthConfig, AuthType

class TestHeaderConfig:
    def test_init_kwargs(self):
        config = HeaderConfig(User_Agent="TestApp", Content_Type="application/json")
        headers = config.to_dict()
        assert headers["User_Agent"] == "TestApp"
        assert headers["Content_Type"] == "application/json"
        
    def test_set_get(self):
        config = HeaderConfig()
        config.set("Connection", "keep-alive")
        assert config.get("Connection") == "keep-alive"
        
    def test_merge(self):
        config = HeaderConfig(A="1")
        config.merge({"B": "2", "C": 3})
        headers = config.to_dict()
        assert headers == {"A": "1", "B": "2", "C": "3"}
        
    def test_set_auth(self):
        config = HeaderConfig()
        auth = AuthConfig(
            type=AuthType.BASIC, 
            username="user", 
            password=SecretStr("pass")
        )
        config.set_auth(auth)
        
        headers = config.to_dict()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        
    def test_set_auth_override(self):
        """Ensure auth headers override existing ones if key matches (though uncommon for Auth to conflict)."""
        config = HeaderConfig(Authorization="Old")
        auth = AuthConfig(type=AuthType.BEARER, token=SecretStr("token"))
        config.set_auth(auth)
        assert config.get("Authorization") == "Bearer token"
