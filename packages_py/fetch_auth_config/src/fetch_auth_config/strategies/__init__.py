from typing import Dict
from ..domain import AuthType
from ..config import AuthConfig
from fetch_auth_encoding import encode_auth

def resolve_auth_headers(config: AuthConfig) -> Dict[str, str]:
    """
    Resolve authentication headers by delegating to fetch-auth-encoding.
    """
    # Prepare arguments from config, extracting secrets
    args = {
        "username": config.username,
        "email": config.email,
        "header_key": config.header_key
    }
    
    if config.password:
        args["password"] = config.password.get_secret_value()
    if config.token:
        args["token"] = config.token.get_secret_value()
    if config.header_value:
        args["header_value"] = config.header_value.get_secret_value()
        
    return encode_auth(config.type.value, **args)
