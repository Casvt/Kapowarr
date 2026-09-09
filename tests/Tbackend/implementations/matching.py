# -*- coding: utf-8 -*-

"""A volume number the filename never stated should not decide the match.

The fixtures are two real ComicVine volumes of one series:

    Detective Comics (1937)  volume 1  issues 1..881
    Detective Comics (2016)  volume 3  issues 934..1112

Issue 962 exists in exactly one of them, and a file named
`Detective.Comics.962.cbz` could only ever reach the other one.
"""

import unittest
from types import SimpleNamespace

from backend.base.definitions import SpecialVersion
from backend.base.file_extraction import extract_filename_data
from backend.implementations.matching import file_importing_filter


def _volume(year, volume_number, first_issue, issue_count):
    volume_data = SimpleNamespace(
        id=1, comicvine_id=1, title='Detective Comics', alt_title=None,
        year=year, volume_number=volume_number, description='', site_url='',
        publisher='DC', monitored=True, monitor_new_issues=True,
        root_folder=1, folder=f'/library/Detective Comics ({year})',
        custom_folder=False, special_version=SpecialVersion.NORMAL,
        special_version_locked=False, last_cv_fetch=0
    )
    issues = [
        SimpleNamespace(calculated_issue_number=float(n), date=None)
        for n in range(first_issue, first_issue + issue_count)
    ]
    number_to_year = {i.calculated_issue_number: None for i in issues}
    return volume_data, issues, number_to_year


DETECTIVE_1937 = _volume(1937, 1, 1, 881)
DETECTIVE_2016 = _volume(2016, 3, 934, 179)


def _accepts(filename, volume):
    volume_data, issues, number_to_year = volume
    # `scan_files` reads names this way for a non-VAI volume.
    file_data = extract_filename_data(filename, assume_volume_number=False)
    return file_importing_filter(
        file_data, volume_data, issues, number_to_year
    )


class file_importing_filter_volume_number(unittest.TestCase):
    def test_name_stating_nothing_reaches_every_volume(self):
        """A name that states neither a volume number nor a year says nothing
        about which volume of the series it belongs to, so the filter must not
        rule any of them out on that absence."""
        self.assertTrue(_accepts('Detective.Comics.962.cbz', DETECTIVE_2016))
        self.assertTrue(_accepts('Detective.Comics.962.cbz', DETECTIVE_1937))

    def test_stated_volume_number_still_decides(self):
        """A volume number the name does state is real evidence, and still
        rules the other volumes out."""
        self.assertTrue(
            _accepts('Detective Comics Vol. 3 962.cbz', DETECTIVE_2016)
        )
        self.assertFalse(
            _accepts('Detective Comics Vol. 3 962.cbz', DETECTIVE_1937)
        )

    def test_stated_year_still_decides(self):
        """A year the name does state is real evidence, in both directions."""
        self.assertTrue(
            _accepts('Detective Comics (1937) 962.cbz', DETECTIVE_1937)
        )
        self.assertFalse(
            _accepts('Detective Comics (1937) 962.cbz', DETECTIVE_2016)
        )
        self.assertTrue(
            _accepts('Detective Comics (2016) 962.cbz', DETECTIVE_2016)
        )
        self.assertFalse(
            _accepts('Detective Comics (2016) 962.cbz', DETECTIVE_1937)
        )
