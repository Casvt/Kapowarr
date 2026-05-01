import unittest

from backend.base.definitions import CredentialSource
from backend.implementations.credentials import Credentials
from backend.implementations.download_client_manager import DownloadClients


class validator_registration(unittest.TestCase):
    def test_all_sources_have_validators(self):
        """Every CredentialSource enum value must have a registered validator."""
        DownloadClients.trigger_client_registration()

        for source in CredentialSource:
            self.assertIn(
                source,
                Credentials.validators,
                f"CredentialSource.{source.name} has no registered validator"
            )
