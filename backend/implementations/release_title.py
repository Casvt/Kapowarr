# -*- coding: utf-8 -*-

"""
Checks on the language of a release, using its name.

Kapowarr matches releases on series title, issue number and year. For
European albums the same series and number exist in several languages
(`Asterix - 36 - De Papyrus van Caesar`, `Asterix T36 Le papyrus de Cesar`,
`Asterix 36 - Der Papyrus des Cäsar`), so on torrent and usenet indexers
those all match. Most of these releases do carry the album title, which is
in the language of the release. Comparing it with the title of the issue on
ComicVine (which is in the language of the volume) tells them apart.
"""

from difflib import SequenceMatcher
from re import IGNORECASE, compile, escape
from typing import TYPE_CHECKING, Iterable, List, Set, Union

from backend.base.definitions import DownloadType
from backend.base.helpers import fully_normalise_string
from backend.internals.db import get_db

if TYPE_CHECKING:
    from backend.base.definitions import IssueData, VolumeData

EXCLUDED_WORDS = (
    "french", "francais", "german", "deutsch", "italian", "italiano",
    "spanish", "espanol", "castellano", "portugues", "polish", "czech"
)
"""
Words that mark a release as being in another language. English isn't in
the list, because most volumes are English.
"""

NOISE_WORDS = {
    "cbr", "cbz", "cb7", "cbt", "pdf", "epub", "zip", "rar", "nzb", "jpg",
    "hq", "lq", "nl", "vl", "fr", "de", "en", "ebook", "ebooks", "rip",
    "scan", "scans", "dpi", "bestanden", "bestand", "comic", "comics",
    "hybrid", "internal", "repack", "proper", "digital", "remastered",
    "new", "strip", "strips", "nieuwe", "c2c", "nr", "deel", "tome", "t",
    "album", "albums", "en", "of"
}
"""
Words that say something about the file, not the album. `de`, `en` and
`of` are language codes here, but also common title words; they're only
dropped when they are the whole remaining title.
"""

TITLE_NOISE_WORDS = NOISE_WORDS - {"de", "en", "of", "deel", "new", "t"}
"Noise words that are never part of an album title"

TITLE_MATCH_THRESHOLD = 0.5
"""
Part of the album title words (of the longest of the two titles) that has
to be exceeded. The issue number already matched, so this only needs to separate
languages, not albums.
"""

WORD_MATCH_RATIO = 0.8
"Similarity for two longer words to count as the same (Caesar/Cesar)"

BRACKETED = compile(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}')
YEAR = compile(r'^(19|20)\d\d$')
WORD = compile(r'[a-z0-9]+')
SCENE_TAIL = compile(
    r'\b(?:hybrid|comic|ebook|cbz|cbr|pdf|internal|repack)\b.*$'
)
"Everything from the first scene tag on in names like `X.T3.Title.2022.FRENCH.HYBRiD.COMiC.CBZ.eBook-GROUP`"


def _normalise(text: str) -> str:
    text = fully_normalise_string(text).lower()
    text = text.replace('_', ' ').replace('.', ' ')
    return text.replace("'", '').replace('’', '')


def _words(text: str) -> List[str]:
    return WORD.findall(text)


def excluded_word_in(release_name: str) -> Union[str, None]:
    """Find a word in the release name that marks it as another language.

    Args:
        release_name (str): The name of the release.

    Returns:
        Union[str, None]: The word, if found.
    """
    words = set(_words(_normalise(release_name)))
    for word in EXCLUDED_WORDS:
        if word in words:
            return word
    return None


def _number_pattern(issue_number: float) -> str:
    if issue_number == int(issue_number):
        number = str(int(issue_number))
    else:
        number = str(issue_number)
    return (
        r'(?<![0-9a-z])(?:t|nr|no|#)?\s*0*'
        + escape(number).replace(r'\.', r'[. ]')
        + r'(?![0-9])'
    )


def album_title(
    release_name: str,
    series_titles: Iterable[str],
    issue_number: float
) -> List[str]:
    """Get the words of the album title out of a release name.

    `Suske en Wiske - 313 - De Kale Kapper (2011) (cbr)` gives
    `['de', 'kale', 'kapper']`.

    Args:
        release_name (str): The name of the release.
        series_titles (Iterable[str]): The title(s) of the volume.
        issue_number (float): The issue number of the release.

    Returns:
        List[str]: The words of the album title, empty if the release name
            doesn't have one.
    """
    text = BRACKETED.sub(' ', _normalise(release_name))

    # Start after the series title, so a number in it isn't used
    start = 0
    for series in series_titles:
        series_words = _words(_normalise(series))
        if not series_words:
            continue
        match = compile(
            r'\b' + r'[^a-z0-9]+'.join(map(escape, series_words)) + r'\b'
        ).search(text)
        if match:
            start = match.end()
            break

    match = compile(_number_pattern(issue_number), IGNORECASE)\
        .search(text, start)
    if not match:
        return []

    rest = SCENE_TAIL.sub('', text[match.end():])
    # A usenet subject repeats the name after the title
    # (`Name - 0222 - Name.cbr.zip.001`); keep the first part
    rest = rest.split(' - 0', 1)[0]

    words = [
        w for w in _words(rest)
        if not YEAR.match(w)
        and w not in TITLE_NOISE_WORDS
        and w not in EXCLUDED_WORDS
    ]
    if all(w in NOISE_WORDS for w in words):
        return []
    return words


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) < 5 or len(b) < 5:
        return False
    if a.startswith(b) or b.startswith(a):
        # A shortened title (`De Planeet` for `De Planeetvreter`)
        return True
    return SequenceMatcher(None, a, b).ratio() >= WORD_MATCH_RATIO


def title_similarity(
    words: List[str],
    issue_title: str,
    series_titles: Iterable[str] = ()
) -> float:
    """How much of the album title matches the issue title.

    Args:
        words (List[str]): The words of the album title of the release.
        issue_title (str): The title of the issue.
        series_titles (Iterable[str], optional): The title(s) of the volume.
            Their words (`Asterix`) are the same in every language, so they
            are left out of the comparison.

    Returns:
        float: The part (0-1) of the words that match, relative to the
            longest of the two titles. 1 when one title contains the other
            completely.
    """
    title_words = _words(_normalise(issue_title))
    if not words or not title_words:
        return 1.0

    if ''.join(words) == ''.join(title_words):
        # Only the spacing differs (`Pedoalarm` and `Pedo-alarm`)
        return 1.0

    series_words = {
        w for s in series_titles for w in _words(_normalise(s))
    }
    stripped = [w for w in words if w not in series_words]
    stripped_title = [w for w in title_words if w not in series_words]
    if stripped and stripped_title:
        words, title_words = stripped, stripped_title

    unused: List[str] = list(title_words)
    matched = 0
    for word in words:
        for candidate in unused:
            if _same_word(word, candidate):
                unused.remove(candidate)
                matched += 1
                break

    if matched >= 2 and matched == min(len(words), len(title_words)):
        # One contains the other (`De Vallei der Onsterfelijken` for
        # `De Vallei der Onsterfelijken: 1 - Dreiging op Hong Kong`)
        return 1.0

    return matched / max(len(words), len(title_words))


def release_title_conflict(
    release_name: str,
    series_titles: Iterable[str],
    issue_number: Union[float, None],
    issue_title: Union[str, None]
) -> Union[str, None]:
    """Check whether a release is the issue in the right language.

    Args:
        release_name (str): The name of the release.
        series_titles (Iterable[str]): The title(s) of the volume.
        issue_number (Union[float, None]): The issue number of the release,
            if it is about one issue.
        issue_title (Union[str, None]): The title of that issue on ComicVine.

    Returns:
        Union[str, None]: Why the release doesn't match, or `None` if it
            matches (or there's not enough information to tell).
    """
    word = excluded_word_in(release_name)
    if word:
        return f"Release is marked as another language ({word})"

    if issue_number is None or not issue_title:
        return None

    words = album_title(release_name, series_titles, issue_number)
    if not words:
        return None

    title_words: Set[str] = set(_words(_normalise(issue_title)))
    if not title_words:
        return None

    similarity = title_similarity(words, issue_title, series_titles)
    if similarity <= TITLE_MATCH_THRESHOLD:
        return (
            f"Album title '{' '.join(words)}' doesn't match issue title "
            f"'{issue_title}'"
        )
    return None


def checks_release_language(indexer_id: Union[int, None]) -> bool:
    """Whether the results of the indexer get the language check. Not for DDL
    indexers: GetComics is English, and its titles often carry the name of a
    story arc instead of the issue title.

    Args:
        indexer_id (Union[int, None]): The ID of the indexer.

    Returns:
        bool: Whether to check the language of its results.
    """
    if indexer_id is None:
        return False
    row = get_db().execute(
        "SELECT download_type FROM indexer_clients WHERE id = ? LIMIT 1;",
        (indexer_id,)
    ).fetchone()
    return bool(row) and row[0] != DownloadType.DDL.value


def release_language_conflict(
    release_name: str,
    volume_data: "VolumeData",
    volume_issues: Iterable["IssueData"],
    issue_number: Union[float, None]
) -> Union[str, None]:
    """`release_title_conflict()` for a release of a volume.

    Args:
        release_name (str): The name of the release.
        volume_data (VolumeData): The data of the volume.
        volume_issues (Iterable[IssueData]): The issues of the volume.
        issue_number (Union[float, None]): The (calculated) issue number of
            the release, if it is about one issue.

    Returns:
        Union[str, None]: Why the release doesn't match, or `None`.
    """
    issue_title = None
    if issue_number is not None:
        for issue in volume_issues:
            if issue.calculated_issue_number == issue_number:
                issue_title = issue.title
                break

    return release_title_conflict(
        release_name,
        [volume_data.title, volume_data.alt_title or ''],
        issue_number,
        issue_title
    )
