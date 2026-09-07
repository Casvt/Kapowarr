# -*- coding: utf-8 -*-

"""Moving a volume carried files belonging to other series with it.

A volume's folder collects files that are not its own -- a directory
shared with another series, or an earlier import that guessed wrong.
Those files end up linked to the volume, and `change_volume_folder` moved
everything the volume was linked to, carrying them deeper into the wrong
series without saying so.

The volume now takes only the files that name it. The rest stay where
they are, on disk and still named by their database row.
"""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.base.logging import LOGGER
from backend.implementations.volumes import Volume


class a_folder_holding_another_series(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.old = os.path.join(self.root, 'Catwoman')
        self.new = os.path.join(self.root, 'Catwoman', 'Catwoman (2018)')
        os.makedirs(self.old)

        self.own = os.path.join(self.old, 'Catwoman 034 (2021).cbz')
        self.stranger = os.path.join(
            self.old, 'Cavewoman - Deep Water 001 (2017).cbz')
        for path in (self.own, self.stranger):
            with open(path, 'wb') as f:
                f.write(b'x')

    def _move(self):
        volume = Volume.__new__(Volume)
        volume.id = 32
        renamed = {}

        def rename(before, after):
            os.makedirs(os.path.dirname(after), exist_ok=True)
            os.replace(before, after)
            renamed[before] = after

        with patch.object(
            Volume, 'get_data',
            return_value=SimpleNamespace(
                title='Catwoman', year=2018, volume_number=1,
                special_version=None, root_folder=1, folder=self.old
            )
        ), patch.object(
            Volume, 'get_all_files',
            return_value=[{'filepath': self.own},
                          {'filepath': self.stranger}]
        ), patch.object(
            Volume, 'update'
        ), patch(
            'backend.implementations.volumes.RootFolders',
            return_value={1: self.root}
        ), patch(
            'backend.implementations.naming.generate_volume_folder_path',
            return_value=self.new
        ), patch(
            'backend.implementations.volumes.rename_file', side_effect=rename
        ), patch(
            'backend.implementations.volumes.FilesDB'
        ) as files_db, patch(
            'backend.implementations.volumes.delete_empty_child_folders'
        ), patch(
            'backend.implementations.volumes.Settings',
            return_value=SimpleNamespace(
                sv=SimpleNamespace(create_empty_volume_folders=False)
            )
        ), patch(
            'backend.implementations.volumes.delete_empty_parent_folders'
        ), patch(
            'backend.implementations.volumes.folder_is_inside_folder',
            return_value=False
        ), patch.object(
            Volume, '_Volume__volume_folder_used_by_other_volume',
            return_value=True
        ), patch(
            'backend.implementations.volumes.mass_process_files'
        ):
            volume.change_volume_folder(None)

        return renamed, files_db

    def test_the_volume_takes_its_own_file(self):
        renamed, _ = self._move()

        self.assertEqual(
            renamed,
            {self.own: os.path.join(self.new, 'Catwoman 034 (2021).cbz')}
        )

    def test_the_other_series_stays_where_it_is(self):
        self._move()

        self.assertTrue(os.path.isfile(self.stranger))
        self.assertFalse(os.path.exists(
            os.path.join(self.new, os.path.basename(self.stranger))))

    def test_the_database_is_not_told_it_moved(self):
        _, files_db = self._move()

        moved = files_db.update_filepaths.call_args[0][0]
        self.assertIn(self.own, moved)
        self.assertNotIn(self.stranger, moved)

    def test_it_says_what_it_left(self):
        with self.assertLogs(LOGGER, level='WARNING') as captured:
            self._move()

        joined = '\n'.join(captured.output)
        self.assertIn('different series', joined)
        self.assertIn('Cavewoman', joined)
