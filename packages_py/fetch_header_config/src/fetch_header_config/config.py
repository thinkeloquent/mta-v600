from typing import Dict, Optional, Any
from fetch_auth_config import AuthConfig, resolve_auth_headers

class HeaderConfig:
    def __init__(self, **kwargs):
        self._headers: Dict[str, str] = {}
        for k, v in kwargs.items():
            self.set(k, v)

    def set(self, key: str, value: Any) -> None:
        """Set a header key-value pair. Converts value to string."""
        # Convert keys to something standard? Usually headers are case-insensitive but stored as given.
        self._headers[key] = str(value)

    def get(self, key: str) -> Optional[str]:
        return self._headers.get(key)
    
    def merge(self, other: Dict[str, Any]) -> None:
        """Merge another dictionary into headers."""
        for k, v in other.items():
            self.set(k, v)

    def set_auth(self, auth_config: AuthConfig) -> None:
        """Resolve and set authentication headers."""
        auth_headers = resolve_auth_headers(auth_config)
        self.merge(auth_headers)

    def to_dict(self) -> Dict[str, str]:
        """Return the final header dictionary."""
        return self._headers.copy()
