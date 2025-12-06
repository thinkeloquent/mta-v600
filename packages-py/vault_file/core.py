# packages-py/vault_file/core.py
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, validator

# Setup logging
logger = logging.getLogger("vault_file")

# Custom Exceptions
class VaultValidationError(Exception):
    """Custom exception for validation errors within the VaultFile."""
    pass

class VaultSerializationError(Exception):
    """Custom exception for errors during serialization or deserialization."""
    pass

# Vault Components
class VaultHeader(BaseModel):
    """
    Header for the VaultFile, containing metadata about the vault itself.
    """
    id: UUID = Field(default_factory=uuid4)
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        validate_assignment = True

class VaultMetadata(BaseModel):
    """
    Metadata for the payload, such as tags, owner, or permissions.
    """
    data: dict = Field(default_factory=dict)

    class Config:
        validate_assignment = True

class VaultPayload(BaseModel):
    """
    The payload of the VaultFile.
    """
    content: dict | list | str

    class Config:
        validate_assignment = True

# Abstract Base Class
class IVaultFile(ABC):
    """
    Interface for the VaultFile.
    """
    @abstractmethod
    def to_json(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def from_json(cls, json_str: str):
        pass

    @abstractmethod
    def validate_state(self):
        pass

# Main VaultFile Class
class VaultFile(BaseModel, IVaultFile):
    """
    A secure and structured container for storing metadata and payload data.
    """
    header: VaultHeader = Field(default_factory=VaultHeader)
    metadata: VaultMetadata = Field(default_factory=VaultMetadata)
    payload: VaultPayload

    def __init__(self, **data):
        super().__init__(**data)
        logger.debug(f"VaultFile initialized with id: {self.header.id}")

    def to_json(self) -> str:
        """Serializes the VaultFile to a JSON string."""
        logger.debug(f"Serializing VaultFile id: {self.header.id}")
        try:
            return self.model_dump_json(indent=2)
        except Exception as e:
            raise VaultSerializationError(f"Failed to serialize to JSON: {e}")

    @classmethod
    def from_json(cls, json_str: str):
        """Deserializes a JSON string to a VaultFile instance."""
        logger.debug("Attempting to deserialize VaultFile from JSON.")
        try:
            return cls.model_validate_json(json_str)
        except Exception as e:
            raise VaultSerializationError(f"Failed to deserialize from JSON: {e}")

    def validate_state(self):
        """Validates the current state of the VaultFile."""
        logger.debug(f"Validating state for VaultFile id: {self.header.id}")
        # Pydantic handles validation on instantiation and assignment
        # This method can be expanded for more complex cross-field validation
        try:
            self.model_validate(self)
        except Exception as e:
            raise VaultValidationError(f"VaultFile state is invalid: {e}")

    class Config:
        validate_assignment = True
