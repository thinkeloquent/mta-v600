# packages-py/vault_file/tests/test_core_structure.py
import pytest
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import patch, MagicMock

from packages_py.vault_file.core import (
    VaultHeader,
    VaultMetadata,
    VaultPayload,
    VaultFile,
    VaultValidationError,
    VaultSerializationError,
)

# Mocking the logger to capture logs
@pytest.fixture
def mock_logger():
    with patch('packages_py.vault_file.core.logger') as mock_log:
        yield mock_log

def test_vault_header_instantiation():
    header = VaultHeader()
    assert isinstance(header.id, UUID)
    assert header.version == "1.0.0"
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
    payload_dict = VaultPayload(content={"key": "value"})
    assert payload_dict.content == {"key": "value"}

    payload_list = VaultPayload(content=[1, 2, 3])
    assert payload_list.content == [1, 2, 3]

    payload_str = VaultPayload(content="hello")
    assert payload_str.content == "hello"

def test_vault_file_instantiation_minimal():
    payload = VaultPayload(content={"test": "data"})
    vault_file = VaultFile(payload=payload)
    assert isinstance(vault_file.header, VaultHeader)
    assert isinstance(vault_file.metadata, VaultMetadata)
    assert vault_file.payload == payload

def test_vault_file_instantiation_full():
    header = VaultHeader(version="1.1.0")
    metadata = VaultMetadata(data={"project": "mta"})
    payload = VaultPayload(content="important info")
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
    payload = VaultPayload(content={"test": "data"})
    vault_file = VaultFile(payload=payload)
    json_str = vault_file.to_json()
    assert isinstance(json_str, str)
    assert "test" in json_str
    assert str(vault_file.header.id) in json_str
    mock_logger.debug.assert_called_with(f"Serializing VaultFile id: {vault_file.header.id}")

def test_vault_file_from_json(mock_logger):
    original_payload_content = {"key": "value", "number": 123}
    original_vault_file = VaultFile(payload=VaultPayload(content=original_payload_content))
    json_str = original_vault_file.to_json()

    new_vault_file = VaultFile.from_json(json_str)

    assert isinstance(new_vault_file, VaultFile)
    assert new_vault_file.header.id == original_vault_file.header.id
    assert new_vault_file.header.version == original_vault_file.header.version
    # Pydantic's datetime handling might change precision, compare components or use isoformat
    assert new_vault_file.header.created_at.replace(microsecond=0) == \
           original_vault_file.header.created_at.replace(microsecond=0)
    assert new_vault_file.metadata.data == original_vault_file.metadata.data
    assert new_vault_file.payload.content == original_vault_file.payload.content
    mock_logger.debug.assert_any_call("Attempting to deserialize VaultFile from JSON.")

def test_vault_file_from_json_invalid_data():
    with pytest.raises(VaultSerializationError):
        VaultFile.from_json("invalid json string")

def test_vault_file_validate_state(mock_logger):
    payload = VaultPayload(content={"data": "test"})
    vault_file = VaultFile(payload=payload)
    vault_file.validate_state() # Should not raise an error
    mock_logger.debug.assert_called_with(f"Validating state for VaultFile id: {vault_file.header.id}")


