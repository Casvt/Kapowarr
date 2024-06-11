import unittest
from json import dumps
from typing import Dict

from backend.file_extraction import extract_filename_data as ef


class extract_filename_data(unittest.TestCase):
    def run_cases(self, cases: Dict[str, dict]):
        self.longMessage = False
        for input, output in cases.items():
            self.assertEqual(
                ef(input),
                output,
                f"The input '{input}' isn't extracted properly:\nOutput: {dumps(ef(input), indent=4)}\nExpected: {dumps(output, indent=4)}"
            )
        return

    def run_cases_folder_year(self, cases: Dict[str, dict]):
        self.longMessage = False
        for input, output in cases.items():
            self.assertEqual(
                ef(input, prefer_folder_year=True),
                output,
                f"The input '{input}' isn't extracted properly:\nOutput: {dumps(ef(input), indent=4)}\nExpected: {dumps(output, indent=4)}"
            )
        return

    # autopep8: off
    def test_general(self):
        cases = {
            'Iron-Man Volume 2 Issue 3.cbr':
                {'series': 'Iron Man', 'year': None, 'volume_number': 2, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            '/plex-media/Comics/Batman/Volume 1 (1940)/Batman (1940) Volume 2 Issue 11-25.zip':
                {'series': 'Batman', 'year': 1940, 'volume_number': 2, 'special_version': None, 'issue_number': (11.0, 25.0), 'annual': False},

            'Tales of the Unexpected, 2006-12-00 (#03) (digital) (Glorith-Novus).cbz':
                {'series': 'Tales of the Unexpected', 'year': 2006, 'volume_number': 1, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            'Tales of the Teen Titans v2 (1984)/Issue 51-58 - Tales of the Teen Titans (1985-03-01)':
                {'series': 'Tales of the Teen Titans', 'year': 1985, 'volume_number': 2, 'special_version': None, 'issue_number': (51.0, 58.0), 'annual': False},

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
                {'series': 'Batman', 'year': 1948, 'volume_number': 1, 'special_version': None, 'issue_number': 48.0, 'annual': False},

            '01. X-Men Vol. 2 (#05, #1 – 113 + Annuals) Part 1 — #1 – 25 --2022-2023--':
                {'series': 'X Men', 'year': 2022, 'volume_number': 2, 'special_version': None, 'issue_number': (1.0, 25.0), 'annual': False},

            'Batman ’66 Meets the Man From U.N.C.L.E. (2016)':
                {'series': 'Batman \'66 Meets the Man From U.N.C.L.E.', 'year': 2016, 'volume_number': 1, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Thor Vol. 3 #1 – 12 (Also known 588-599) + #600 – 621 (2007-2011) --2007-2011--':
                {'series': 'Thor', 'year': 2007, 'volume_number': 3, 'special_version': None, 'issue_number': (600.0, 621.0), 'annual': False},

            'Aliens Life And Death #003 (2016) Volume 02.cbr':
                {'series': 'Aliens Life And Death', 'year': 2016, 'volume_number': 2, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            '/home/cas/plex-media/Comics/Invincible Compendium/Volume 1/Invincible Compendium Volume 2 Issue 3 - Volume 4 (2018-07-18).cbr':
                {'series': 'Invincible Compendium', 'year': 2018, 'volume_number': 2, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            'Batman and the Mad Monk (1-6) (2006-2007) GetComics.INFO/Batman___The_Mad_Monk_02__2007___team-ocdcp_.cbr':
                {'series': 'Batman The Mad Monk', 'year': 2007, 'volume_number': 1, 'special_version': None, 'issue_number': 2.0, 'annual': False},

            '/comics-1/Heroes for Hire/Heroes for Hire # ½ 02-2005.cbr':
                {'series': 'Heroes for Hire', 'year': 2005, 'volume_number': 1, 'special_version': None, 'issue_number': 0.5, 'annual': False},

            'Spider-Man (2005) #3 - The Vector Attacks! - [01-02-2006] [cv-123]':
                {'series': 'Spider Man', 'year': 2005, 'volume_number': 1, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            'Captain America (2018) Issue 025 - All Die Young Part VI; The Promise':
                {'series': 'Captain America', 'year': 2018, 'volume_number': 1, 'special_version': None, 'issue_number': 25.0, 'annual': False},

            'Wolverine (2020) Issue 006 - X of Swords, Chapter 3':
                {'series': 'Wolverine', 'year': 2020, 'volume_number': 1, 'special_version': None, 'issue_number': 6.0, 'annual': False},

            'Batman Annual (1961) Volume 1 Issue 10/90 - Batman_Annual #10/Batman Annual #10-02.jpg':
                {'series': 'Batman Annual', 'year': 1961, 'volume_number': 1, 'special_version': None, 'issue_number': 10.0, 'annual': True},

            'Action Comics (2011) #31 - Infected Chapter 1 True Believers':
                {'series': 'Action Comics', 'year': 2011, 'volume_number': 1, 'special_version': None, 'issue_number': 31.0, 'annual': False},

            'The Wicked + The Divine (2014) - 035 1-2-3-4! ; The Curse in My Hands - [2018-04-30]':
                {'series': 'The Wicked The Divine', 'year': 2014, 'volume_number': 1, 'special_version': None, 'issue_number': 35.0, 'annual': False},

            'Avengers Classic #1 – 12 (2007-2008)':
                {'series': 'Avengers Classic', 'year': 2007, 'volume_number': 1, 'special_version': None, 'issue_number': (1.0, 12.0), 'annual': False},

            'Spider-Man Chapter One 002(1999).cbr':
                {'series': 'Spider Man Chapter One', 'year': 1999, 'volume_number': 1, 'special_version': None, 'issue_number': 2.0, 'annual': False},

            'Spider-Man Chapter One 002-004(1999).cbr':
                {'series': 'Spider Man Chapter One', 'year': 1999, 'volume_number': 1, 'special_version': None, 'issue_number': (2.0, 4.0), 'annual': False},
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
                {'series': 'Silver Surfer Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Silver Surfer - Rebirth (2022) (HD-WebRip) - 011.cbr':
                {'series': 'Silver Surfer Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': None, 'issue_number': 11.0, 'annual': False},

            'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Page-100.jpg':
                {'series': 'Silver Surfer Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/Page - 100.jpg':
                {'series': 'Silver Surfer Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Silver Surfer - Rebirth (2022) (HD-WebRip) Volume 2/100.jpg':
                {'series': 'Silver Surfer Rebirth', 'year': 2022, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Star Wars Darth Vader (2020) Volume 3 Issue 18/Star Wars - Darth Vader (2021-) 019-002.jpg':
                {'series': 'Star Wars Darth Vader', 'year': 2021, 'volume_number': 3, 'special_version': None, 'issue_number': 18.0, 'annual': False}
        }
        self.run_cases(cases)

    def test_cover(self):
        cases = {
            'Batman Annual (1961) Volume 1 Issue 1-28/Batman - Annuals (1-28) (1961-2011) GetComics.INFO/Batman Annual 006 (1964) (no cover).cbr':
                {'series': 'Batman Annual', 'year': 1964, 'volume_number': 1, 'special_version': None, 'issue_number': 6.0, 'annual': True},

            'Batman_Annual_n02c01':
                {'series': 'Batman Annual', 'year': None, 'volume_number': 1, 'special_version': 'cover', 'issue_number': 2.0, 'annual': True},

            'Batman Annual (1961) Volume 1 Issue 1-28/Batman - Annuals (1-28) (1961-2011) GetComics.INFO/Batman Annual cover (1964).cbr':
                {'series': 'Batman Annual', 'year': 1964, 'volume_number': 1, 'special_version': 'cover', 'issue_number': None, 'annual': True},

            'Batman Annual (1961) Volume 1 Issue 1-28/Batman - Annuals (1-28) (1961-2011) GetComics.INFO/Batman Annual v2c6 (1964).cbr':
                {'series': 'Batman Annual', 'year': 1964, 'volume_number': 2, 'special_version': None, 'issue_number': 6.0, 'annual': True},

            'Batman Annual (1961) Volume 1 Issue 16/Batman-Annual-1992-16-00-FC.jpg':
                {'series': 'Batman Annual', 'year': 1992, 'volume_number': 1, 'special_version': 'cover', 'issue_number': 16.0, 'annual': True},

            'Batman Annual (1961) Volume 1 Issue 13/Batman-Annual #13-00fc.jpg':
                {'series': 'Batman Annual', 'year': 1961, 'volume_number': 1, 'special_version': 'cover', 'issue_number': 13.0, 'annual': True},

            'Batman Annual (1961) Volume 1 Issue 14/Batman-Annual #14-00.jpg':
                {'series': 'Batman Annual', 'year': 1961, 'volume_number': 1, 'special_version': None, 'issue_number': 14.0, 'annual': True},

            'Action Comics/Volume 2 (2011)/Action Comics 000 (2012) (4 covers) (digital) (Minutemen-PhD).cbr':
                {'series': 'Action Comics', 'year': 2012, 'volume_number': 2, 'special_version': None, 'issue_number': 0.0, 'annual': False},

            'Undiscovered Country Volume 2 Issue 3.cbr':
                {'series': 'Undiscovered Country', 'year': None, 'volume_number': 2, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            'Undiscovered Country Volume 2 Issue 3/Undiscovered Country Volume 2 Issue 3 Cover.jpg':
                {'series': 'Undiscovered Country', 'year': None, 'volume_number': 2, 'special_version': 'cover', 'issue_number': 3.0, 'annual': False},

            'Iron-Man (1980) Volume 2 One-Shot Cover':
                {'series': 'Iron Man', 'year': 1980, 'volume_number': 2, 'special_version': 'cover', 'issue_number': None, 'annual': False}
        }
        self.run_cases(cases)

    def test_folder_year(self):
        cases = {
            'Iron Man/Volume 1 (1945)/Iron Man Volume 1 Issue 100 (02-03-1950).cbr':
                {'series': 'Iron Man', 'year': 1945, 'volume_number': 1, 'special_version': None, 'issue_number': 100.0, 'annual': False},

            'Iron Man/Volume 1/Iron Man Volume 1 Issue 100 (02-03-1950).cbr':
                {'series': 'Iron Man', 'year': 1950, 'volume_number': 1, 'special_version': None, 'issue_number': 100.0, 'annual': False},
        }
        self.run_cases_folder_year(cases)

    def test_special_version(self):
        cases = {
            'Superman Lost Volume 2 Issue 3.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': None, 'issue_number': 3.0, 'annual': False},

            'Superman Lost Volume 2.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 Issue 3 TPB.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 Trade paper BACK.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'tpb', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 OS.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'one-shot', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 One Shot.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'one-shot', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 ONE-SHOT.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'one-shot', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 Hc.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'hard-cover', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 Hard Cover.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'hard-cover', 'issue_number': None, 'annual': False},

            'Superman Lost Volume 2 Issue 3 HARD-COVER.cbr':
                {'series': 'Superman Lost', 'year': None, 'volume_number': 2, 'special_version': 'hard-cover', 'issue_number': None, 'annual': False},

            'Iron Man Vol. 2 #1 – 13 + TPB (1996-1997 + 2006)':
                {'series': 'Iron Man', 'year': 1996, 'volume_number': 2, 'special_version': None, 'issue_number': (1.0, 13.0), 'annual': False}
        }
        self.run_cases(cases)
    # autopep8: on