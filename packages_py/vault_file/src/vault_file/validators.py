
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class VaultValidationError(Exception):
    """Custom exception for vault validation errors."""
    pass

class VaultSerializationError(Exception):
    """Custom exception for vault serialization errors."""
    pass


def validate_vault_data(data: Dict[str, Any]) -> None:
    """
    Validates the structure and content of vault data.
    Raises VaultValidationError if the data is invalid.
    """
    logger.debug("Validating vault data")
    if "header" not in data:
        raise VaultValidationError("Missing 'header' in vault data")
    if "metadata" not in data:
        raise VaultValidationError("Missing 'metadata' in vault data")
    if "payload" not in data:
        raise VaultValidationError("Missing 'payload' in vault data")
    
    validate_header(data["header"])
    logger.debug("Vault data validation successful")

def validate_header(header_data: Dict[str, Any]) -> None:
    """
    Validates the header of the vault data.
    """
    logger.debug("Validating vault header")
    required_keys = ["version", "created_at", "id"]
    for key in required_keys:
        if key not in header_data:
            raise VaultValidationError(f"Missing '{key}' in header")
    logger.debug("Vault header validation successful")

