from typing import Dict
import unittest

from backend.files import extract_filename_data as ef

class extract_filename_data(unittest.TestCase):
	def run_cases(self, cases: Dict[str, dict]):
		self.longMessage = False
		for input, output in cases.items():
			self.assertEqual(ef(input), output, f"'{input}' isn't extracted properly")
		return

	def test_general(self):
		cases = {
		    'Iron-Man Volume 2 Issue 3.cbr':
				{'series': 'Iron-Man', 'year': None, 'volume_number': 2, 'special_version': None, 'issue_number': 3.0, 'annual': False},

			'/plex-media/Comics/Batman/Volume 1 (1940)/Batman (1940) Volume 2 Issue 11-25.zip':
				{'series': 'Batman', 'year': 1940, 'volume_number': 2, 'special_version': None, 'issue_number': (11.0, 25.0), 'annual': False},

			'Tales of the Unexpected, 2006-12-00 (#03) (digital) (Glorith-Novus).cbz':
				{'series': 'Tales of the Unexpected', 'year': 2006, 'volume_number': 1, 'special_version': None, 'issue_number': 3.0, 'annual': False},

			'Tales of the Teen Titans v2 (1984)/Issue 51-58 - Tales of the Teen Titans (1985-03-01)':
				{'series': 'Tales of the Teen Titans', 'year': 1984, 'volume_number': 2, 'special_version': None, 'issue_number': (51.0, 58.0), 'annual': False},

			'Doctor Strange, Sorcerer Supreme Volume 2 Issues #4.0-4.5 (03-2022)':
				{'series': 'Doctor Strange, Sorcerer Supreme', 'year': 2022, 'volume_number': 2, 'special_version': None, 'issue_number': (4.0, 4.5), 'annual': False},

			'The Incredible Hulk/Volume III/5-6 - The Incredible Hulk (2022).epub':
				{'series': 'The Incredible Hulk', 'year': 2022, 'volume_number': 3, 'special_version': None, 'issue_number': (5.0, 6.0), 'annual': False},

			'John Constantine, Hellblazer: 30th Anniversary Celebration (2018)/John Constantine, Hellblazer: 30th Anniversary Celebration (2018) - 5.zip':
				{'series': 'John Constantine, Hellblazer: 30th Anniversary Celebration', 'year': 2018, 'volume_number': 1, 'special_version': None, 'issue_number': 5.0, 'annual': False},

			'Team 7 v1 (2012)/Team 7 (0-8) GetComics.INFO/Team 7 008.cbr':
				{'series': 'Team 7', 'year': 2012, 'volume_number': 1, 'special_version': None, 'issue_number': 8.0, 'annual': False},

			'Infinity Gauntlet #1 – 6 (1991-1992)':
				{'series': 'Infinity Gauntlet', 'year': 1991, 'volume_number': 1, 'special_version': None, 'issue_number': (1.0, 6.0), 'annual': False},

      '1. Infinity Gauntlet #2 - 100 (1999-2009)':
				{'series': 'Infinity Gauntlet', 'year': 1999, 'volume_number': 1, 'special_version': None, 'issue_number': (2.0, 100.0), 'annual': False},

			'100 Bullets #1 - 101 (1999-2009)':
				{'series': '100 Bullets', 'year': 1999, 'volume_number': 1, 'special_version': None, 'issue_number': (1.0, 101.0), 'annual': False},

      'Batman 026-050 (1945-1949) GetComics.INFO/Batman 048 52p ctc (08-1948) flattermann.cbr':
				{'series': 'Batman', 'year': 1945, 'volume_number': 1, 'special_version': None, 'issue_number': 48.0, 'annual': False}
		}
		self.run_cases(cases)

	def test_other_languages(self):
		cases = {
			'52 Томa 3 Issue 3-5 (2022)':
				{'series': '52', 'year': 2022, 'volume_number': 3, 'special_version': None, 'issue_number': (3.0, 5.0), 'annual': False},

			'Team 6 7Том':
				{'series': 'Team 6', 'year': None, 'volume_number': 7, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

			'Kid Colt 第5卷 01-02-2022 c8':
				{'series': 'Kid Colt', 'year': 2022, 'volume_number': 5, 'special_version': None, 'issue_number': 8.0, 'annual': False},

			'Batman & Robin 2권 Issues#5-8a + Annuals (2000-2005).cbr':
				{'series': 'Batman & Robin', 'year': 2000, 'volume_number': 2, 'special_version': None, 'issue_number': (5.0, 8.01), 'annual': False}
		}
		self.run_cases(cases)

	def test_annuals(self):
		cases = {
			'Avengers (1996) Volume 2 Annuals.zip':
				{'series': 'Avengers', 'year': 1996, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': True},

			'Avengers (1996) Volume 3 + Annuals.zip':
				{'series': 'Avengers', 'year': 1996, 'volume_number': 3, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

			'Avengers (1996) Volume 4 Annuals + Issue 5.zip':
				{'series': 'Avengers', 'year': 1996, 'volume_number': 4, 'special_version': None, 'issue_number': 5.0, 'annual': False},

			'Avengers Annuals (1996) v3/c6.cbr':
				{'series': 'Avengers Annuals', 'year': 1996, 'volume_number': 3, 'special_version': None, 'issue_number': 6.0, 'annual': True},

			'Avengers + Annuals (1996) v3/c #6-7 ½ + annual.cbr':
				{'series': 'Avengers Annuals', 'year': 1996, 'volume_number': 3, 'special_version': None, 'issue_number': (6.0, 7.5), 'annual': False}
		}
		self.run_cases(cases)

	def test_page_vs_issue(self):
		cases = {
			'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Silver Surfer - Rebirth (2022) (HD-WebRip) - 011.jpg':
				{'series': 'Silver Surfer - Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},
			'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Silver Surfer - Rebirth (2022) (HD-WebRip) - 011.cbr':
				{'series': 'Silver Surfer - Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': None, 'issue_number': 11.0, 'annual': False},
			'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Page-100.cbr':
				{'series': 'Silver Surfer - Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': None, 'issue_number': 100.0, 'annual': False},
			'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Page-100.jpg':
				{'series': 'Silver Surfer - Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False}
		}
		self.run_cases(cases)
