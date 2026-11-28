import unittest

from backend.implementations.release_title import (album_title,
                                                   release_title_conflict,
                                                   title_similarity)


class AlbumTitle(unittest.TestCase):
    def test_title_after_number(self):
        self.assertEqual(
            album_title(
                'Suske en Wiske - 313 - De Kale Kapper (2011) (cbr)',
                ['Suske en Wiske'],
                313.0
            ),
            ['de', 'kale', 'kapper']
        )

    def test_number_in_series_title_is_skipped(self):
        self.assertEqual(
            album_title(
                'XIII - 13 - Het XX dossier (1999)',
                ['XIII'],
                13.0
            ),
            ['het', 'xx', 'dossier']
        )

    def test_scene_name(self):
        self.assertEqual(
            album_title(
                'Asterix.T36.Le.Papyrus.de.Cesar.2015.FRENCH.HYBRiD.COMiC.CBZ.eBook-GROUP',
                ['Asterix'],
                36.0
            ),
            ['le', 'papyrus', 'de', 'cesar']
        )

    def test_no_title(self):
        self.assertEqual(
            album_title('Batman 012 (2020) (Digital)', ['Batman'], 12.0),
            []
        )


class TitleSimilarity(unittest.TestCase):
    def test_spelling_variation(self):
        self.assertEqual(
            title_similarity(
                ['de', 'papyrus', 'van', 'cesar'],
                'De Papyrus van Caesar'
            ),
            1.0
        )

    def test_spacing_difference(self):
        self.assertEqual(
            title_similarity(['pedoalarm'], 'Pedo-alarm'),
            1.0
        )

    def test_title_contains_other(self):
        self.assertEqual(
            title_similarity(
                ['de', 'vallei', 'der', 'onsterfelijken'],
                'De Vallei der Onsterfelijken: 1 - Dreiging op Hong Kong'
            ),
            1.0
        )

    def test_other_language(self):
        self.assertLess(
            title_similarity(
                ['le', 'papyrus', 'de', 'cesar'],
                'De Papyrus van Caesar'
            ),
            1.0
        )


class ReleaseTitleConflict(unittest.TestCase):
    def test_same_language(self):
        self.assertIsNone(release_title_conflict(
            'Asterix - 36 - De Papyrus van Caesar (2015)',
            ['Asterix'],
            36.0,
            'De Papyrus van Caesar'
        ))

    def test_language_tag(self):
        self.assertIsNotNone(release_title_conflict(
            'Asterix 36 Der Papyrus des Casar (2015) (German)',
            ['Asterix'],
            36.0,
            'De Papyrus van Caesar'
        ))

    def test_title_in_other_language(self):
        self.assertIsNotNone(release_title_conflict(
            'Kiekeboe 150 - Le Grand Secret (2015)',
            ['Kiekeboe'],
            150.0,
            'Het Grote Geheim'
        ))

    def test_not_enough_information(self):
        self.assertIsNone(release_title_conflict(
            'Asterix 36 (2015)', ['Asterix'], 36.0, 'De Papyrus van Caesar'
        ))
        self.assertIsNone(release_title_conflict(
            'Asterix - 36 - De Papyrus van Caesar', ['Asterix'], None, None
        ))
