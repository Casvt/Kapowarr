import unittest

import backend.implementations.direct_clients.mega
import backend.implementations.download_clients
from backend.base.definitions import CredentialSource
from backend.implementations.credentials import Credentials


class validator_registration(unittest.TestCase):
    def test_all_sources_have_validators(self):
        """Every CredentialSource enum value must have a registered validator."""
        for source in CredentialSource:
            self.assertIn(
                source,
                Credentials.validators,
                f"CredentialSource.{source.name} has no registered validator"
            )
