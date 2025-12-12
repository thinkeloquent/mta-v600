import base64
import pytest
from fetch_auth_encoding import encode_auth

def b64(s):
    return base64.b64encode(s.encode()).decode()

class TestEncodeAuth:
    # --- Basic Family ---
    def test_basic(self):
        h = encode_auth("basic", username="u", password="p")
        assert h == {"Authorization": f"Basic {b64('u:p')}"}
        
    def test_basic_email_token(self):
        h = encode_auth("basic_email_token", email="e", token="t")
        assert h == {"Authorization": f"Basic {b64('e:t')}"}

    def test_basic_token(self):
        h = encode_auth("basic_token", username="u", token="t")
        assert h == {"Authorization": f"Basic {b64('u:t')}"}

    def test_basic_email(self):
        h = encode_auth("basic_email", email="e", password="p")
        assert h == {"Authorization": f"Basic {b64('e:p')}"}

    # --- Bearer Family ---
    def test_bearer(self):
        h = encode_auth("bearer", token="raw_tok")
        assert h == {"Authorization": "Bearer raw_tok"}
        
    def test_bearer_oauth(self):
        h = encode_auth("bearer_oauth", token="oauth_tok")
        assert h == {"Authorization": "Bearer oauth_tok"}
        
    def test_bearer_username_token(self):
        h = encode_auth("bearer_username_token", username="u", token="t")
        assert h == {"Authorization": f"Bearer {b64('u:t')}"}
        
    def test_bearer_email_password(self):
        h = encode_auth("bearer_email_password", email="e", password="p")
        assert h == {"Authorization": f"Bearer {b64('e:p')}"}
        
    # --- Custom ---
    def test_x_api_key(self):
        h = encode_auth("x-api-key", value="key123")
        assert h == {"X-API-Key": "key123"}
        
    def test_custom(self):
        h = encode_auth("custom", header_key="K", header_value="V")
        assert h == {"K": "V"}
        
    # --- Errors ---
    def test_missing_args(self):
        with pytest.raises(ValueError, match="requires"):
            encode_auth("basic", username="u") # missing password
