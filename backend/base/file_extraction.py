# -*- coding: utf-8 -*-

"""
Extracting comic data from a string and generalising it.
The string can be a filepath, filename or search result title, etc.
"""

from os.path import basename, dirname, splitext
from re import IGNORECASE, Pattern, compile
from typing import Collection, Dict, Tuple, Union, Optional

from backend.base.definitions import (CONTENT_EXTENSIONS, CharConstants,
                                      FileConstants, FilenameData,
                                      SpecialVersion)
from backend.base.helpers import (check_overlapping_pos,
                                  fix_year as fix_broken_year,
                                  normalise_number, normalise_string)
from backend.base.logging import LOGGER
from backend.base.files import (clean_filestring_simple, clean_filestring_smartly)


# autopep8: off
alphabet = {
    letter: str(CharConstants.ALPHABET.index(letter) + 1).zfill(2)
    for letter in CharConstants.ALPHABET
}

volume_regex_snippet = r'\b(?:v(?:ol|olume)?)(?:\.\s|[\.\-\s])?(\d+(?:(?:\-|\s\-\s|\.\-\.)\d+)?|(?<!v)I{1,3})'
year_regex_snippet = r'(?:(\d{4})(?:-\d{2}){0,2}|(\d{4})[\s\.]?[\-\s](?:[\s\.]?\d{4})?|(?:\d{2}-){1,2}(\d{4})|(\d{4})[\s\.\-_]Edition|(\d{4})\-\d{4}\s{3}\d{4})'
issue_regex_snippet = r'(?!\d+(?:p|th|rd|st|\s?(?:gb|mb|kb)))(?<!\')(?<!cv[\s\-_])(?:\d+(?:\.\d{1,2}|\.?[a-z0-9]+|[\s\-\._]?[½¼])?|[½¼∞])'

# Cleaning the filename
strip_filename_regex = compile(r'\(.*?\)|\[.*?\]|\{.*?\}', IGNORECASE)

# Supporting languages by translating them
russian_volume_regex = compile(r'Томa?[\s\.]?(\d+)', IGNORECASE)
russian_volume_regex_2 = compile(r'(\d+)[\s\.]?Томa?', IGNORECASE)
chinese_volume_regex = compile(r'第(\d+)(?:卷|册)', IGNORECASE)
chinese_volume_regex_2 = compile(r'(?:卷|册)(\d+)', IGNORECASE)
korean_volume_regex = compile(r'제?(\d+)권', IGNORECASE)
japanese_volume_regex = compile(r'(\d+)巻', IGNORECASE)
french_issue_regex = compile(r'\bT(?:omes?)?(?=[\s\.]?\d)', IGNORECASE)

# Extract data from (stripped)filename
special_version_regex = compile(r'(?:(?<!\s{3})\b|\()(?:(?P<tpb>tpb|trade paper back)|(?P<one_shot>os|one[ \-_]?shot)|(?P<hard_cover>hc|hard[ \-_]?cover)|(?P<omnibus>omnibus))(?:\b|\))', IGNORECASE)
volume_regex = compile(volume_regex_snippet, IGNORECASE)
volume_folder_regex = compile(volume_regex_snippet + r'|^(\d+)$', IGNORECASE)
issue_regex = compile(r'\(_(\-?' + issue_regex_snippet + r')\)', IGNORECASE)
issue_regex_2 = compile(r'(?:(?<!\()(?:(?<![a-z])c(?!2c)|\bissues?|\bbooks?)(?!\))|no)(?:\.?[\s\-_]?|\s\-\s)(?:#\s*)?(\-?' + issue_regex_snippet + r'(?:(?:\-|\s\-\s|\.\-\.)\-?' + issue_regex_snippet + r')?)\b', IGNORECASE)
issue_regex_3 = compile(r'(?<!part[\s\._])(' + issue_regex_snippet + r')[\s\-\._]?\(?[\s\-\._]?of[\s\-\._]?' + issue_regex_snippet + r'(?![\s\-\._]covers)\)?(?=\s|\.|_|(?=\()|$)', IGNORECASE)
issue_regex_4 = compile(r'(?<!--)(?<!annual\s)(?<!pages\s)(?:#\s*)?(\-?' + issue_regex_snippet + r'(?:\-|\s\-\s|\.\-\.)' + issue_regex_snippet + r')(?=\s|\.|_|(?=\()|$)', IGNORECASE)
issue_regex_5 = compile(r'(?<!page\s)#\s*(\-?' + issue_regex_snippet + r')\b(?!(?:\-|\s\-\s|\.\-\.)' + issue_regex_snippet + r')', IGNORECASE)
issue_regex_6 = compile(r'(?:(?P<i_start>^)|(?<=(?<!part)(?<!page)[\s\._])(?P<n_c>n))(\-?' + issue_regex_snippet + r')(?=(?(n_c)c\d+|\s\-)(?=\s|\.|_|(?=\()|$))', IGNORECASE)
issue_regex_7 = compile(r'(?:(?<=\s|\.|_)|(?<=^))(\-?' + issue_regex_snippet + r')(?![\s\-\._]covers?)(?![\s\-\._]of[\s\-\._]\d+[\s\-\._]covers?)(?=\s|\.|_|\(|$)', IGNORECASE)
year_regex = compile(r'\((?:[a-z]+\.?\s)?' + year_regex_snippet + r'\)|--' + year_regex_snippet + r'--|__' + year_regex_snippet + r'__|, ' + year_regex_snippet + r'\s{3}|\b(?:(?:\d{2}-){1,2}(\d{4})|(\d{4})(?:-\d{2}){1,2})\b', IGNORECASE)
series_regex = compile(r'(^(\d+\.)?\s+|^\d+\s{3}|\s(?=\s)|[\s,]+$)')
annual_regex = compile(r'(?:\+|plus)[\s\._]?annuals?|annuals?[\s\._]?(?:\+|plus)|^((?!annuals?).)*$', IGNORECASE) # If regex matches, it's NOT an annual
cover_regex = compile(r'\b(?<!no[ \-_])(?<!hard[ \-_])(?<!\d[ \-_]covers)cover\b|n\d+c(\d+)|(?:\b|\d)i?fc\b|^folder$', IGNORECASE)
page_regex = compile(r'^(\d+(?:[a-f]|_\d+)?)$|\b(?i:page|pg)[\s\.\-_]?(\d+(?:[a-f]|_\d+)?)|n?\d+[_\-p](\d+(?:[a-f]|_\d+)?)')
page_regex_2 = compile(r'(\d+)')
# autopep8: on


def _calculated_issue_number(issue_number: str) -> Union[float, None]:
    """Convert an issue number from string to representive float.

    Args:
        issue_number (str): The issue number to convert.

    Returns:
        Union[float, None]: Either the float version or `None` on fail.
    """
    try:
        # Number is already a valid float, just in string form.
        return float(issue_number)
    except ValueError:
        pass

    # Issue has special number notation
    issue_number = normalise_number(issue_number)

    # Negative or not
    if issue_number.startswith('-'):
        converted_issue_number = '-'
    else:
        converted_issue_number = ''

    digits = CharConstants.DIGITS
    dot = True
    for char in issue_number:
        if char in digits:
            converted_issue_number += char

        else:
            if char == '∞':
                converted_issue_number += '9999999999999'

            elif dot:
                converted_issue_number += '.'
                dot = False

            if char == '½':
                converted_issue_number += '5'

            elif char == '¼':
                converted_issue_number += '3'

            elif char in alphabet:
                converted_issue_number += alphabet.get(char, alphabet['z'])

    if converted_issue_number.strip('.'):
        return float(converted_issue_number)

    return None


def process_issue_number(
    issue_number: str
) -> Union[float, Tuple[float, float], None]:
    """Convert an issue number or issue range to a (tuple of) float(s).

    ```
    >>> process_issue_number('2b')
    2.02
    >>> process_issue_number('2b-4')
    (2.02, 4.0)
    ```

    Args:
        issue_number (str): The issue number.

    Returns:
        Union[float, Tuple[float, float], None]: The converted issue number(s) or
            `None` if unsuccessful.
    """
    issue_number = issue_number.replace('/', '-')

    if '-' not in issue_number[1:]:
        # Normal issue number
        return _calculated_issue_number(issue_number)

    # Issue range
    start, end = issue_number[1:].replace(' ', '').split('-', 1)
    start = issue_number[0] + start

    if not (
        start.lstrip('-')[0] in CharConstants.DIGITS
        and end.lstrip('-')[0] in CharConstants.DIGITS
    ):
        # Not both the start and end are starting with a (negative) number, so
        # the idea that the input is a range was false.
        return _calculated_issue_number(issue_number)

    calc_start = _calculated_issue_number(start)
    calc_end = _calculated_issue_number(end)

    if calc_start is not None:
        if calc_end is not None:
            return (calc_start, calc_end)
        return calc_start

    elif calc_end is not None:
        return calc_end

    return None


def process_volume_number(
    volume_number: Union[str, None]
) -> Union[int, Tuple[int, int], None]:
    """Convert a volume number or volume range to a (tuple of) int(s). Also
    supports roman numerals.

    ```
    >>> process_volume_number('2')
    2
    >>> process_volume_number('2-4')
    (2, 4)
    >>> process_volume_number('IV')
    4
    ```

    Args:
        volume_number (Union[str, None]): The volume number (range) in string
            format. Or `None`, which will return `None`.

    Returns:
        Union[int, Tuple[int, int], None]: The converted volume number(s) or
            `None` if the input was also `None`.
    """
    if volume_number is None:
        return None

    # If volume number is a straight 1-10 roman numeral, then convert it.
    volume_number = str(
        CharConstants.ROMAN_DIGITS.get(
            volume_number.lower(),
            volume_number
        )
    )

    result = process_issue_number(volume_number)
    if isinstance(result, float):
        result = int(result)
    elif isinstance(result, tuple):
        result = int(result[0]), int(result[1])
    return result


def _translate_filepath(filepath: str) -> str:
    filepath = french_issue_regex.sub("Issue", filepath)
    if 'Том' in filepath:
        filepath = russian_volume_regex.sub(r'Volume \1', filepath)
        filepath = russian_volume_regex_2.sub(r'Volume \1', filepath)
    if '第' in filepath or '卷' in filepath or '册' in filepath:
        filepath = chinese_volume_regex.sub(r'Volume \1', filepath)
        filepath = chinese_volume_regex_2.sub(r'Volume \1', filepath)
    if '권' in filepath:
        filepath = korean_volume_regex.sub(r'Volume \1', filepath)
    if '巻' in filepath:
        filepath = japanese_volume_regex.sub(r'Volume \1', filepath)
    return filepath


def _extensionless_filename(filepath: str) -> str:
    filename = basename(filepath)
    if splitext(filename)[1].lower() in CONTENT_EXTENSIONS:
        filename = splitext(filename)[0]
    return filename


def _find_issue_numbers(
    pos_options: Collection[Tuple[str, Dict[str, int], Tuple[Pattern, ...]]]
):
    for file_part_with_issue, pos_option, regex_list in pos_options:
        for regex in regex_list:
            regex_result = list(regex.finditer(
                file_part_with_issue, **pos_option
            ))
            if not regex_result:
                continue

            group_number = 1 if regex is not issue_regex_6 else 3
            for result in reversed(regex_result):
                yield (
                    result.group(group_number),
                    result.start(0), result.end(0)
                )


def extract_filename_data(
    filepath: str,
    assume_volume_number: bool = True,
    prefer_folder_year: bool = False,
    fix_year: bool = False,
    assume_title: Optional[str] = None
) -> FilenameData:
    """Extract comic data from a string and generalise it. The string can be a
    filepath, filename or search result title, etc.

    ```
    >>> extract_filename_data(
        "/Comics/Batman/Volume 1 (1940)/Batman (1940) Volume 2 Issue 11-25.zip"
    )
    {
        "series": "Batman",
        "year": 1940,
        "volume_number": 2,
        "special_version": None,
        "issue_number": (11.0, 25.0),
        "annual": False
    }
    ```

    Args:
        filepath (str): The source string.

        assume_volume_number (bool, optional): If no volume number was found,
            should `1` be assumed? When a series has only one volume, often the
            volume number isn't included in the filename.
            Defaults to True.

        prefer_folder_year (bool, optional): Use year in foldername instead of
            year in filename, if available.
            Defaults to False.

        fix_year (bool, optional): If the extracted year is most likely broken,
            fix it. See `helpers.fix_year()`.
            Defaults to False.

    Returns:
        FilenameData: The extracted data.
    """
    LOGGER.debug(f'Extracting filename data: {filepath}')
    series, year, volume_number, special_version, issue_number = (
        None, None, None, None, None
    )

    # Remove title from filepath if present, makes sure we don't get issueNumber from volume title
    if assume_title:
        filepath = filepath.replace(clean_filestring_smartly(assume_title), "")
        filepath = filepath.replace(clean_filestring_simple(assume_title), "")

    # Process folder if file is metadata file, as metadata filename contains
    # no useful information.
    is_metadata_file = (
        basename(filepath.lower())
        in FileConstants.METADATA_FILES
    )
    if is_metadata_file:
        filepath = dirname(filepath)
        special_version = SpecialVersion.METADATA.value

    # Generalise filename
    filepath = _translate_filepath(normalise_string(filepath))

    # Determine whether it's an annual
    annual_result = annual_regex.search(basename(filepath))
    annual_folder_result = annual_regex.search(basename(dirname(filepath)))
    annual = not (annual_result and annual_folder_result)
    filepath = filepath.replace('+', ' ')

    # Prepare some variables
    is_image_file = filepath.endswith(FileConstants.IMAGE_EXTENSIONS)
    foldername = basename(dirname(filepath))
    upper_foldername = basename(dirname(dirname(filepath)))
    filename = _extensionless_filename(filepath)
    # Stripped version of filename without (), {}, [] and extension
    clean_filename = strip_filename_regex.sub(
        lambda m: " " * len(m.group()), filename
    ) + ' '

    # Get year
    all_year_pos, all_year_folderpos = [(10_000, 10_000)], [(10_000, 10_000)]

    if prefer_folder_year:
        year_order = (foldername, filename, upper_foldername)
    else:
        year_order = (filename, foldername, upper_foldername)

    for location in year_order:
        year_result = list(year_regex.finditer(location))
        if year_result:
            if year is None:
                year = next(
                    y
                    for y in year_result[0].groups()
                    if y
                )

            if location == filename:
                all_year_pos = [
                    (r.start(0), r.end(0))
                    for r in year_result
                ]

            if location == foldername:
                all_year_folderpos = [
                    (r.start(0), r.end(0))
                    for r in year_result
                ]

    # Get volume number
    volume_result = None
    volume_pos, volume_end, volume_folderpos, volume_folderend = (
        10_000, 0, 10_000, 0
    )
    if not is_image_file:
        volume_result = volume_regex.search(clean_filename)
        if volume_result:
            # Volume number found (e.g. Series Volume 1 Issue 6.ext)
            volume_number = process_volume_number(volume_result.group(1))
            volume_pos = volume_result.start(0)
            volume_end = volume_result.end(1)

    # Find volume match in folder for finding series name
    # (or when volume number couldn't be found in filename)
    volume_folder_result = volume_folder_regex.search(foldername)
    if volume_folder_result:
        # Volume number found in folder (e.g. Series Volume 1/Issue 5.ext)
        volume_folderpos = volume_folder_result.start(0)
        volume_folderend = volume_folder_result.end(0)
        if not volume_result:
            volume_number = process_volume_number(
                volume_folder_result.group(1) or volume_folder_result.group(2)
            )

    if (
        assume_volume_number
        and not volume_result
        and not volume_folder_result
    ):
        volume_number = 1

    # Get special version
    issue_pos, issue_folderpos = 10_000, 10_000
    special_pos, special_end = 10_000, 0
    if not special_version:
        cover_result = cover_regex.search(filename)
        if cover_result:
            special_version = SpecialVersion.COVER.value
            if cover_result.group(1):
                special_pos = cover_result.start(1)
                special_end = cover_result.end(1)
            else:
                special_pos = cover_result.start(0)
                special_end = cover_result.end(0)

        else:
            special_result = special_version_regex.search(filename)
            if special_result:
                special_version = [
                    k for k, v in special_result.groupdict().items()
                    if v is not None
                ][0].replace('_', '-')
                special_pos = special_result.start(0)

    # Get issue number
    if special_version not in (
        None,
        SpecialVersion.COVER,
        SpecialVersion.METADATA
    ):
        # Special version, so don't search for issue number
        pass

    elif not is_image_file:
        pos_options = (
            (filename,
                {'pos': volume_end},
                (issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
                    issue_regex_5, issue_regex_6, issue_regex_7)),
            (filename,
                {'endpos': volume_pos},
                (issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
                    issue_regex_5, issue_regex_6))
        )

        for extracted_number, result_start, result_end in _find_issue_numbers(
            pos_options
        ):
            if not check_overlapping_pos(
                all_year_pos + [(special_pos, special_end)],
                (result_start, result_end)
            ):
                issue_number = extracted_number
                issue_pos = result_start
                break

    else:
        pos_options = (
            (foldername,
                {'pos': volume_folderend},
                (issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
                    issue_regex_5, issue_regex_6, issue_regex_7)),
            (foldername,
                {'endpos': volume_folderpos},
                (issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
                    issue_regex_5, issue_regex_6))
        )

        for extracted_number, result_start, result_end in _find_issue_numbers(
            pos_options
        ):
            if not check_overlapping_pos(
                all_year_folderpos,
                (result_start, result_end)
            ):
                issue_number = extracted_number
                issue_folderpos = result_start
                break

    if not issue_number and not special_version:
        special_version = SpecialVersion.TPB.value

    # Get series
    series_pos = min(
        all_year_pos[0][0],
        volume_pos,
        special_pos,
        issue_pos
    )
    if series_pos and not is_image_file:
        # Series name is assumed to be in the filename,
        # left of all other information
        series = clean_filename[:series_pos - 1]
    else:
        series_folder_pos = min(
            all_year_folderpos[0][0], volume_folderpos, issue_folderpos
        )
        if series_folder_pos:
            # Series name is assumed to be in the foldername,
            # left of all other information
            series = foldername[:series_folder_pos - 1]
        else:
            # Series name is assumed to be the upper foldername
            series = strip_filename_regex.sub('', upper_foldername)
    series = series_regex.sub('', series.replace('-', ' ').replace('_', ' '))

    # Format output
    if issue_number is not None:
        calculated_issue_number = process_issue_number(issue_number)
    else:
        calculated_issue_number = None

    year = int(year) if year else None
    if fix_year and year is not None:
        year = fix_broken_year(year)

    if assume_title:
        series = clean_filestring_simple(assume_title)

    file_data = FilenameData({
        'series': assume_title or series,
        'year': year,
        'volume_number': volume_number,
        'special_version': special_version,
        'issue_number': calculated_issue_number,
        'annual': annual
    })

    LOGGER.debug(f'Extracting filename data: {file_data}')

    return file_data
