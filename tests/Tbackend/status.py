import unittest

from backend.base.definitions import StatusType
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
