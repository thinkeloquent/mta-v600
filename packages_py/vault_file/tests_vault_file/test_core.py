
import unittest
import json
import os
from datetime import datetime, timedelta
import uuid
from vault_file.core import VaultFile, VaultHeader, VaultMetadata, VaultPayload
from vault_file.validators import VaultValidationError, VaultSerializationError

class TestVaultFile(unittest.TestCase):

    def test_round_trip_serialization(self):
        """
        Tests that a VaultFile object can be serialized to JSON and deserialized back
        to an equivalent object.
        """
        header = VaultHeader(version="1.1", created_at=datetime.now(), id=uuid.uuid4())
        metadata = VaultMetadata(data={"owner": "test-user", "tags": ["test", "example"]})
        payload = VaultPayload(data={"secret": "my-secret-data"})
        
        original_vault_file = VaultFile(header=header, metadata=metadata, payload=payload)
        
        # Manually create the expected dictionary before serialization
        expected_dict = {
            "header": {
                "version": header.version,
                "created_at": header.created_at.isoformat(),
                "id": str(header.id)
            },
            "metadata": metadata.data,
            "payload": {"data": payload.data}
        }
        
        json_str = original_vault_file.to_json()
        
        # Verify the JSON string matches the expected structure and content
        self.assertEqual(json.loads(json_str), expected_dict)
        
        deserialized_vault_file = VaultFile.from_json(json_str)
        
        # Compare fields of the original and deserialized objects
        self.assertEqual(original_vault_file.header.version, deserialized_vault_file.header.version)
        self.assertAlmostEqual(original_vault_file.header.created_at, deserialized_vault_file.header.created_at, delta=timedelta(seconds=1))
        self.assertEqual(original_vault_file.header.id, deserialized_vault_file.header.id)
        self.assertEqual(original_vault_file.metadata.data, deserialized_vault_file.metadata.data)
        self.assertEqual(original_vault_file.payload.data, deserialized_vault_file.payload.data)


    def test_file_io(self):
        """
        Tests that a VaultFile object can be saved to and loaded from disk.
        """
        vault_file = VaultFile(
            metadata=VaultMetadata(data={"purpose": "file_io_test"})
        )
        test_path = "test_vault_file.json"

        # Ensure file doesn't exist before test
        if os.path.exists(test_path):
            os.remove(test_path)

        try:
            vault_file.save_to_disk(test_path)
            self.assertTrue(os.path.exists(test_path))

            loaded_vault_file = VaultFile.load_from_disk(test_path)
            self.assertEqual(vault_file.metadata.data, loaded_vault_file.metadata.data)

        finally:
            # Clean up the created file
            if os.path.exists(test_path):
                os.remove(test_path)

    def test_validation_error(self):
        """
        Tests that from_json raises VaultSerializationError for invalid data.
        """
        invalid_json_str = '{"metadata": {}, "payload": {}}'
        with self.assertRaises(VaultSerializationError):
            VaultFile.from_json(invalid_json_str)

if __name__ == '__main__':
    unittest.main()
