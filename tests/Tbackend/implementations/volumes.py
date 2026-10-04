import unittest
from unittest.mock import MagicMock, patch

from backend.base.definitions import IssueSorting
from backend.implementations.volumes import Volume


class issue_sorting(unittest.TestCase):
    """`Volume.get_issues()` should order by whichever `IssueSorting` is
    requested, defaulting to `IssueSorting.DATE` when none is given.
    """

    @patch("backend.implementations.volumes.get_db")
    def test_issue_number_sort_is_used_as_the_order_by(
            self, get_db: MagicMock):
        cursor = get_db.return_value
        cursor.execute.return_value.fetchalldict.return_value = []

        Volume(1).get_issues(_skip_files=True, sort=IssueSorting.ISSUE_NUMBER)

        query = cursor.execute.call_args[0][0]
        self.assertIn(f"ORDER BY {IssueSorting.ISSUE_NUMBER.value}", query)

    @patch("backend.implementations.volumes.get_db")
    def test_title_sort_is_used_as_the_order_by(self, get_db: MagicMock):
        cursor = get_db.return_value
        cursor.execute.return_value.fetchalldict.return_value = []

        Volume(1).get_issues(_skip_files=True, sort=IssueSorting.TITLE)

        query = cursor.execute.call_args[0][0]
        self.assertIn(f"ORDER BY {IssueSorting.TITLE.value}", query)

    @patch("backend.implementations.volumes.get_db")
    def test_default_sort_is_date(self, get_db: MagicMock):
        """No `sort` argument should fall back to `IssueSorting.DATE`,
        matching the behavior before per-column sorting was added.
        """
        cursor = get_db.return_value
        cursor.execute.return_value.fetchalldict.return_value = []

        Volume(1).get_issues(_skip_files=True)

        query = cursor.execute.call_args[0][0]
        self.assertIn(f"ORDER BY {IssueSorting.DATE.value}", query)
