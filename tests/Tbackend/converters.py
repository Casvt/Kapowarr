# -*- coding: utf-8 -*-

"""A failed conversion must not delete the file it was given.

`rar_to_zip` extracts a `.cbr` into a scratch folder, zips that folder and
then deletes the original, without checking that the extraction worked --
`run_rar` returns a `CompletedProcess` and nothing looks at its return
code. When rar fails it leaves the folder empty, and `create_zip_archive`
on an empty folder writes a valid ZIP with no entries: exactly 22 bytes,
an end-of-central-directory record and nothing else. The file record is
then repointed at that stub and the source removed, so the issue counts as
complete and holds no comic.

`zip_to_rar` has the same shape and one worse consequence: it deletes the
source and returns a path to a `.rar` it never confirmed exists.
"""

import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from backend.implementations import converters


class _Rar:
    "Stands in for `run_rar`, which returns a CompletedProcess."

    def __init__(self, returncode=0, writes=None):
        self.returncode = returncode
        self.writes = writes or {}

    def __call__(self, args):
        for path, content in self.writes.items():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(content)
        return SimpleNamespace(returncode=self.returncode, stdout='', stderr='')


class a_failed_extraction_keeps_the_original(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.volume_folder = os.path.join(self.tmp.name, 'volume')
        self.workspace = os.path.join(self.tmp.name, 'extract')
        os.makedirs(self.volume_folder)

        self.source = os.path.join(self.volume_folder, 'Comic 001.cbr')
        with open(self.source, 'wb') as f:
            f.write(b'Rar!\x1a\x07\x00' + b'x' * 4096)

        for target, value in (
            ('FilesDB', SimpleNamespace(volume_of_file=lambda f: 1)),
            ('Volume', lambda vid: SimpleNamespace(
                vd=SimpleNamespace(folder=self.volume_folder))),
            ('generate_archive_folder', lambda vf, f: self.workspace),
        ):
            patcher = patch.object(converters, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _rar(self, rar):
        return patch.object(converters, 'run_rar', rar)

    def test_a_nonzero_exit_leaves_the_comic_alone(self):
        with self._rar(_Rar(returncode=3)):
            result = converters.rar_to_zip(self.source)

        self.assertEqual(result, [self.source])
        self.assertTrue(os.path.isfile(self.source))
        self.assertEqual(os.path.getsize(self.source), 4103)

    def test_an_extraction_that_produced_nothing_leaves_it_alone(self):
        with self._rar(_Rar(returncode=0)):
            result = converters.rar_to_zip(self.source)

        self.assertEqual(result, [self.source])
        self.assertTrue(os.path.isfile(self.source))

    def test_no_empty_archive_is_left_behind(self):
        with self._rar(_Rar(returncode=0)):
            converters.rar_to_zip(self.source)

        stub = os.path.join(self.volume_folder, 'Comic 001.zip')
        self.assertFalse(os.path.exists(stub))
        self.assertFalse(os.path.exists(self.workspace))

    def test_a_real_extraction_still_converts(self):
        page = os.path.join(self.workspace, 'page01.jpg')
        with self._rar(_Rar(returncode=0, writes={page: b'\xff\xd8' * 200})):
            result = converters.rar_to_zip(self.source)

        target = os.path.join(self.volume_folder, 'Comic 001.zip')
        self.assertEqual(result, [target])
        self.assertTrue(os.path.isfile(target))
        self.assertFalse(os.path.exists(self.source))
        with zipfile.ZipFile(target) as archive:
            self.assertEqual(archive.namelist(), ['page01.jpg'])


class an_empty_archive_is_recognised(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _zip(self, name, entries):
        path = os.path.join(self.tmp.name, name)
        with zipfile.ZipFile(path, 'w') as archive:
            for entry in entries:
                archive.writestr(entry, b'x')
        return path

    def test_an_archive_with_no_entries(self):
        path = self._zip('empty.cbz', [])
        self.assertEqual(os.path.getsize(path), 22)
        self.assertTrue(converters.archive_is_empty(path))

    def test_an_archive_with_a_page_in_it(self):
        self.assertFalse(
            converters.archive_is_empty(self._zip('ok.cbz', ['page01.jpg']))
        )

    def test_something_that_is_not_an_archive_at_all(self):
        path = os.path.join(self.tmp.name, 'broken.cbz')
        with open(path, 'wb') as f:
            f.write(b'not a zip')
        self.assertTrue(converters.archive_is_empty(path))
