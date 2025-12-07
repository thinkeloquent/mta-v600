
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class VaultHeader:
    """
    Data class for the header of a vault file.
    """
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "id": str(self.id)
        }

@dataclass
class VaultMetadata:
    """
    Data class for the metadata of a vault file.
    """
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.data

@dataclass
class VaultPayload:
    """
    Data class for the payload of a vault file.
    """
    data: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {"data": self.data}


class IVaultFile(ABC):
    """
    Abstract base class for a vault file.
    """

    @abstractmethod
    def to_json(self) -> str:
        """
        Serializes the vault file to a JSON string.
        """
        pass

    @classmethod
    @abstractmethod
    def from_json(cls, json_str: str) -> 'IVaultFile':
        """
        Deserializes a JSON string to a vault file object.
        """
        pass

    @abstractmethod
    def save_to_disk(self, path: str) -> None:
        """
        Saves the vault file to disk.
        """
        pass

    @classmethod
    @abstractmethod
    def load_from_disk(cls, path: str) -> 'IVaultFile':
        """
        Loads a vault file from disk.
        """
        pass

@dataclass
class VaultFile(IVaultFile):
    """
    A class representing a vault file.
    """
    header: VaultHeader = field(default_factory=VaultHeader)
    metadata: VaultMetadata = field(default_factory=VaultMetadata)
    payload: VaultPayload = field(default_factory=VaultPayload)

    def to_json(self) -> str:
        import json
        logger.debug("Serializing VaultFile to JSON")
        return json.dumps({
            "header": self.header.to_dict(),
            "metadata": self.metadata.to_dict(),
            "payload": self.payload.to_dict()
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'VaultFile':
        import json
        from .validators import validate_vault_data

        logger.debug("Deserializing VaultFile from JSON")
        data = json.loads(json_str)
        
        # This is where validation would be called
        # validate_vault_data(data)

        header = VaultHeader(
            version=data["header"]["version"],
            created_at=datetime.fromisoformat(data["header"]["created_at"]),
            id=uuid.UUID(data["header"]["id"])
        )
        metadata = VaultMetadata(data=data["metadata"])
        payload = VaultPayload(data=data["payload"]["data"])

        return cls(header, metadata, payload)
        
    def save_to_disk(self, path: str) -> None:
        logger.debug(f"Saving vault file to {path}")
        # Atomic write: write to temp file then rename
        temp_path = f"{path}.tmp"
        try:
            with open(temp_path, 'w') as f:
                f.write(self.to_json())
            import os
            os.rename(temp_path, path)
            logger.info(f"Vault file saved successfully to {path}")
        except Exception as e:
            logger.error(f"Failed to save vault file to {path}: {e}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    @classmethod
    def load_from_disk(cls, path: str) -> 'VaultFile':
        logger.debug(f"Loading vault file from {path}")
        try:
            with open(path, 'r') as f:
                json_str = f.read()
            return cls.from_json(json_str)
        except FileNotFoundError:
            logger.error(f"Vault file not found at {path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load vault file from {path}: {e}")
            raise

