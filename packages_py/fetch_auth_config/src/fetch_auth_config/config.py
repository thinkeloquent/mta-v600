from typing import Optional, Dict
from pydantic import BaseModel, SecretStr, Field
from .domain import AuthType

class AuthConfig(BaseModel):
    type: AuthType
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    email: Optional[str] = None
    token: Optional[SecretStr] = None
    header_key: Optional[str] = None
    header_value: Optional[SecretStr] = None
    
    # Allow extra fields for custom strategies if needed
    model_config = {"extra": "allow"}
