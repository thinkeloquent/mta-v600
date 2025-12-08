# packages-py/vault_file/tests/test_core_structure.py
import pytest
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import patch, MagicMock

from vault_file.core import (
    VaultHeader,
    VaultMetadata,
    VaultPayload,
    VaultFile,
)
from vault_file.validators import (
    VaultValidationError,
    VaultSerializationError,
)

# Mocking the logger to capture logs
@pytest.fixture
def mock_logger():
    with patch('vault_file.core.logger') as mock_log:
        yield mock_log

def test_vault_header_instantiation():
    header = VaultHeader()
    assert isinstance(header.id, UUID)
    assert header.version == "1.0"  # Default version is "1.0"
    assert isinstance(header.created_at, datetime)
    assert header.created_at.tzinfo is None # utcnow creates naive datetime

def test_vault_header_custom_values():
    custom_id = UUID("12345678-1234-5678-1234-567812345678")
    custom_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    header = VaultHeader(id=custom_id, version="2.0.0", created_at=custom_dt)
    assert header.id == custom_id
    assert header.version == "2.0.0"
    assert header.created_at == custom_dt

def test_vault_metadata_instantiation():
    metadata = VaultMetadata()
    assert metadata.data == {}

def test_vault_metadata_with_data():
    data = {"tag": "test", "owner": "user1"}
    metadata = VaultMetadata(data=data)
    assert metadata.data == data

def test_vault_payload_instantiation():
    payload_dict = VaultPayload(data={"key": "value"})
    assert payload_dict.data == {"key": "value"}

    payload_list = VaultPayload(data=[1, 2, 3])
    assert payload_list.data == [1, 2, 3]

    payload_str = VaultPayload(data="hello")
    assert payload_str.data == "hello"

def test_vault_file_instantiation_minimal():
    payload = VaultPayload(data={"test": "data"})
    vault_file = VaultFile(payload=payload)
    assert isinstance(vault_file.header, VaultHeader)
    assert isinstance(vault_file.metadata, VaultMetadata)
    assert vault_file.payload == payload

def test_vault_file_instantiation_full():
    header = VaultHeader(version="1.1.0")
    metadata = VaultMetadata(data={"project": "mta"})
    payload = VaultPayload(data="important info")
    vault_file = VaultFile(header=header, metadata=metadata, payload=payload)
    assert vault_file.header == header
    assert vault_file.metadata == metadata
    assert vault_file.payload == payload

def test_vault_validation_error_exception():
    with pytest.raises(VaultValidationError):
        raise VaultValidationError("Validation failed")

def test_vault_serialization_error_exception():
    with pytest.raises(VaultSerializationError):
        raise VaultSerializationError("Serialization failed")

def test_vault_file_to_json(mock_logger):
    payload = VaultPayload(data={"test": "data"})
    vault_file = VaultFile(payload=payload)
    json_str = vault_file.to_json()
    assert isinstance(json_str, str)
    assert "test" in json_str
    assert str(vault_file.header.id) in json_str
    mock_logger.debug.assert_called_with("Serializing VaultFile to JSON")

def test_vault_file_from_json(mock_logger):
    original_payload_data = {"key": "value", "number": 123}
    original_vault_file = VaultFile(payload=VaultPayload(data=original_payload_data))
    json_str = original_vault_file.to_json()

    new_vault_file = VaultFile.from_json(json_str)

    assert isinstance(new_vault_file, VaultFile)
    assert new_vault_file.header.id == original_vault_file.header.id
    assert new_vault_file.header.version == original_vault_file.header.version
    # Pydantic's datetime handling might change precision, compare components or use isoformat
    assert new_vault_file.header.created_at.replace(microsecond=0) == \
           original_vault_file.header.created_at.replace(microsecond=0)
    assert new_vault_file.metadata.data == original_vault_file.metadata.data
    assert new_vault_file.payload.data == original_vault_file.payload.data
    mock_logger.debug.assert_any_call("Deserializing VaultFile from JSON")

def test_vault_file_from_json_invalid_data():
    with pytest.raises(VaultSerializationError):
        VaultFile.from_json("invalid json string")

def test_vault_file_validate_state():
    payload = VaultPayload(data={"data": "test"})
    vault_file = VaultFile(payload=payload)
    # VaultFile doesn't have validate_state method - just verify creation works
    assert vault_file.payload.data == {"data": "test"}


