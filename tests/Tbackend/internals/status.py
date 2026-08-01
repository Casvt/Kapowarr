import unittest
from datetime import datetime, timedelta
from time import time

from backend.base.definitions import DownloadService, StatusType
from backend.internals.status import StatusHandlers


class status_handler_registration(unittest.TestCase):
    def test_all_status_types_have_handlers(self):
        """Every StatusType enum value must have a registered handler."""
        for status_type in StatusType:
            self.assertIn(
                status_type,
                StatusHandlers.handlers,
                f"StatusType.{status_type.name} has no registered handler"
            )

    def test_download_service_rate_limit_expires_at_next_midnight(self):
        """Download-service rate-limit status should expire at the next midnight."""
        handler = StatusHandlers.handlers[StatusType.DOWNLOAD_SERVICE_RATE_LIMIT]
        timestamp = int(time())
        expected = int(
            (
                datetime.fromtimestamp(timestamp)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                + timedelta(days=1)
            ).timestamp()
        )

        self.assertEqual(
            handler.get_expiry(
                DownloadService.MEGA.value,
                timestamp),
            expected)
