import unittest
from typing import Dict

from backend.base.definitions import FilenameData
from backend.base.file_extraction import extract_filename_data
from backend.features.library_import import create_groups


class CreateGroupsTests(unittest.TestCase):
    def test_groups_ignore_year_for_same_volume(self):
        files: Dict[str, FilenameData] = {
            'Iron Man Volume 1 Issue 2': extract_filename_data(
                'Iron Man Volume 1 Issue 2'
            ),
            'Iron Man Volume 1 Issue 3': extract_filename_data(
                'Iron Man Volume 1 Issue 3'
            )
        }

        groups = create_groups(files)

        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[1].keys()), set(files.keys()))

    def test_groups_detect_volume_as_issue_matches(self):
        files: Dict[str, FilenameData] = {
            'Iron Man Volume 1 Issue 2': extract_filename_data(
                'Iron Man Volume 1 Issue 2'
            ),
            'Iron Man Volume 1 Issue 3': extract_filename_data(
                'Iron Man Volume 1 Issue 3'
            ),
            'Iron Man Volume 2': extract_filename_data(
                'Iron Man Volume 2'
            ),
            'Iron Man Volume 3': extract_filename_data(
                'Iron Man Volume 3'
            )
        }

        groups = create_groups(files)

        self.assertEqual(len(groups), 2)
        self.assertEqual(set(groups[1].keys()), {
            "Iron Man Volume 1 Issue 2",
            "Iron Man Volume 1 Issue 3"
        })
        self.assertEqual(set(groups[2].keys()), {
            "Iron Man Volume 2",
            "Iron Man Volume 3"
        })

    def test_groups_require_sequential_years_and_issue_numbers(self):
        files: Dict[str, FilenameData] = {
            'Iron Man Volume 1 Issue 2 (2025)': extract_filename_data(
                'Iron Man Volume 1 Issue 2 (2025)'
            ),
            'Iron Man Volume 1 Issue 3 (2026)': extract_filename_data(
                'Iron Man Volume 1 Issue 3 (2026)'
            ),
            'Iron Man Volume 1 Issue 5 (2026)': extract_filename_data(
                'Iron Man Volume 1 Issue 5 (2026)'
            )
        }

        groups = create_groups(files)
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[1].keys()), set(files.keys()))
