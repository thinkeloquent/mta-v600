import base64
from typing import Dict, Optional, Any

def _base64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")

def encode_auth(auth_type: str, **kwargs: Any) -> Dict[str, str]:
    """
    Encodes authentication credentials into HTTP headers based on the auth type.
    
    Args:
        auth_type: The type of authentication (e.g., 'basic', 'bearer', 'x-api-key').
        **kwargs: credentials like username, password, email, token, header_key, header_value.
        
    Returns:
        A dictionary containing the HTTP headers.
    """
    auth_type = auth_type.lower()
    
    # Extract common credentials
    username = kwargs.get("username")
    password = kwargs.get("password")
    email = kwargs.get("email")
    token = kwargs.get("token")
    
    # --- Basic Auth Family ---
    if auth_type == "basic":
        # Auto-compute: prefer email:token, then email:password, then username:token, then username:password
        # The prompt says "auto-compute from available credentials".
        # Let's try to be smart or just strict on what's available.
        # RFC 7617 defaults to username:password.
        
        user_part = username or email
        secret_part = password or token
        
        if not user_part or not secret_part:
            raise ValueError("Basic auth requires username/email and password/token")
            
        credentials = f"{user_part}:{secret_part}"
        return {"Authorization": f"Basic {_base64_encode(credentials)}"}

    if auth_type == "basic_email_token":
        if not email or not token: raise ValueError("basic_email_token requires email and token")
        return {"Authorization": f"Basic {_base64_encode(f'{email}:{token}')}"}

    if auth_type == "basic_token":
        if not username or not token: raise ValueError("basic_token requires username and token")
        return {"Authorization": f"Basic {_base64_encode(f'{username}:{token}')}"}

    if auth_type == "basic_email":
        if not email or not password: raise ValueError("basic_email requires email and password")
        return {"Authorization": f"Basic {_base64_encode(f'{email}:{password}')}"}

    # --- Bearer Auth Family ---
    
    if auth_type in ["bearer", "bearer_oauth", "bearer_jwt"]:
        # Simple Bearer <token>
        # For 'bearer', the prompt says "Auto-compute (raw token or encoded credentials)"
        # But usually 'bearer' just takes a single token value.
        val = token or password # Fallback if someone passes password as token?
        if not val: raise ValueError(f"{auth_type} requires token")
        return {"Authorization": f"Bearer {val}"}

    if auth_type == "bearer_username_token":
        if not username or not token: raise ValueError("bearer_username_token requires username and token")
        return {"Authorization": f"Bearer {_base64_encode(f'{username}:{token}')}"}

    if auth_type == "bearer_username_password":
        if not username or not password: raise ValueError("bearer_username_password requires username and password")
        return {"Authorization": f"Bearer {_base64_encode(f'{username}:{password}')}"}

    if auth_type == "bearer_email_token":
        if not email or not token: raise ValueError("bearer_email_token requires email and token")
        return {"Authorization": f"Bearer {_base64_encode(f'{email}:{token}')}"}

    if auth_type == "bearer_email_password":
        if not email or not password: raise ValueError("bearer_email_password requires email and password")
        return {"Authorization": f"Bearer {_base64_encode(f'{email}:{password}')}"}

    # --- Custom/API Key ---
    
    if auth_type == "x-api-key":
        # Format: X-API-Key: <raw_api_key>
        # Where does raw_api_key come from? Likely 'token' or specific arg?
        # Let's assume 'token' or 'key' or 'value'
        val = token or kwargs.get("value") or kwargs.get("key")
        if not val: raise ValueError("x-api-key requires token/value")
        return {"X-API-Key": val}

    if auth_type in ["custom", "custom_header"]:
        key = kwargs.get("header_key")
        val = kwargs.get("header_value") or kwargs.get("value")
        if not key: raise ValueError(f"{auth_type} requires header_key")
        return {key: val or ""}

    # --- HMAC (Stub) ---
    if auth_type == "hmac":
        raise NotImplementedError("HMAC auth not yet fully implemented")

    if auth_type == "none":
        return {}

    raise ValueError(f"Unsupported auth type: {auth_type}")
