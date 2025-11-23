import unittest
import tempfile
import os
import sys

# Add the project to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.internals.db import DB_SCHEMA


class TestDatabaseSchema(unittest.TestCase):
    """Test that the database schema includes all necessary tables."""

    def test_indexers_table_in_schema(self):
        """Test that the indexers table definition exists in DB_SCHEMA."""
        self.assertIn(
            'CREATE TABLE IF NOT EXISTS indexers',
            DB_SCHEMA,
            "indexers table definition must be present in DB_SCHEMA"
        )
        # Verify key columns are defined
        self.assertIn('id INTEGER PRIMARY KEY', DB_SCHEMA)
        self.assertIn('name VARCHAR(255) NOT NULL', DB_SCHEMA)
        self.assertIn('base_url TEXT NOT NULL', DB_SCHEMA)
        self.assertIn('api_key TEXT NOT NULL', DB_SCHEMA)
        self.assertIn("indexer_type VARCHAR(20) NOT NULL DEFAULT 'newznab'", DB_SCHEMA)

    def test_prowlarr_config_table_in_schema(self):
        """Test that the prowlarr_config table definition exists in DB_SCHEMA."""
        self.assertIn(
            'CREATE TABLE IF NOT EXISTS prowlarr_config',
            DB_SCHEMA,
            "prowlarr_config table definition must be present in DB_SCHEMA"
        )


if __name__ == '__main__':
    unittest.main()
