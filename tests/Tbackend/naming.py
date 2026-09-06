import unittest
from os.path import join
from tempfile import TemporaryDirectory

from backend.implementations.naming import same_name_indexing


class SameNameIndexing(unittest.TestCase):
    def test_collision_in_nonexistent_folder(self):
        with TemporaryDirectory() as temporary_folder:
            volume_folder = join(temporary_folder, 'new-volume')
            destination = join(volume_folder, 'name.cbz')
            planned_renames = {
                join(temporary_folder, 'first.cbz'): destination,
                join(temporary_folder, 'second.cbz'): destination
            }

            result = same_name_indexing(volume_folder, planned_renames)

            self.assertIs(result, planned_renames)
            self.assertEqual(
                list(result.values()),
                [destination, join(volume_folder, 'name (1).cbz')]
            )
