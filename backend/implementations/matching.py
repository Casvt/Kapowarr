# -*- coding: utf-8 -*-

"""
All matching is done here. Can be between file and database,
file and CV result, issue/volume and GC result, etc.
"""

from __future__ import annotations

from re import compile
from typing import TYPE_CHECKING, List, Mapping, Tuple, Union

from backend.base.definitions import SpecialVersion
from backend.base.helpers import create_range, extract_year_from_date
from backend.implementations.blocklist import blocklist_contains

if TYPE_CHECKING:
    from backend.base.definitions import (FilenameData, SearchResultData,
                                          SearchResultMatchData)
    from backend.implementations.volumes import VolumeData

clean_title_regex = compile(
    r'((?<=annual)s|/|\-|–|\+|,|\.|\!|:|\bthe\s|\band\b|&|’|\'|\"|\bone-shot\b|\btpb\b)'
)


def _match_title(
    title1: str,
    title2: str,
    allow_contains: bool = False
) -> bool:
    """Determine if two titles match; if they refer to the same thing.

    Args:
        title1 (str): The first title.
        title2 (str): The second title, to which the first title should be
        compared.
        allow_contains (bool, optional): Also match if title2 is found somewhere
        in title1.

    Returns:
        bool: Whether the titles match.
    """
    clean_reference_title = clean_title_regex.sub(
        '',
        title1.lower()
    ).replace(' ', '')

    clean_title = clean_title_regex.sub(
        '',
        title2.lower()
    ).replace(' ', '')

    if allow_contains:
        return clean_title in clean_reference_title
    else:
        return clean_reference_title == clean_title


def _match_year(
    reference_year: Union[int, None],
    check_year: Union[int, None],
    end_year: Union[int, None] = None,
    conservative: bool = False
) -> bool:
    """Check if two years match, with one year of 'wiggle room'.

    Args:
        reference_year (Union[int, None]): The year to check against.

        check_year (Union[int, None]): The year to check.

        end_year (Union[int, None], optional): A different year as the end
        border. Supply `None` to disable and use reference_year for both borders
        instead.
            Defaults to None.

        conservative (bool, optional): If either of the years is `None`,
        play it safe and return `True`.
            Defaults to False.

    Returns:
        bool: Whether the years match.
    """
    if reference_year is None or check_year is None:
        return conservative

    end_border = end_year or reference_year

    return reference_year - 1 <= check_year <= end_border + 1


def _match_volume_number(
    volume_data: VolumeData,
    volume_issues: List[dict],
    check_number: Union[None, int, Tuple[int, int]],
    conservative: bool = False
) -> bool:
    """Check if the volume number matches the one of the volume or it's year.
    If Special Version is VAI, then the volume number (or range) should
    match to an issue number in the volume.

    Args:
        volume_data (VolumeData): The data of the volume.

        volume_issues (List[dict]): The data of the issues of the volume.

        check_number (Union[None, int, Tuple[int, int]]): The volume number
        (or range) to check.

        conservative (bool, optional): If either of the volume numbers is `None`,
        play it safe and return `True`.
            Defaults to False.

    Returns:
        bool: Whether the volume numbers match.
    """
    if (volume_data.volume_number, volume_data.year) == (None, None):
        return conservative

    if check_number is None:
        return conservative

    if isinstance(check_number, int):
        if check_number == volume_data.volume_number:
            return True

        if _match_year(volume_data.year, check_number):
            return True

    # Volume numbers don't match, but
    # it's possible that the volume is volume-as-issue.
    # Then the volume number is actually the issue number.
    # So check if an issue exists with the volume number.

    if volume_data.special_version != SpecialVersion.VOLUME_AS_ISSUE:
        return False

    number_found = 0
    numbers = (
        check_number
        if isinstance(check_number, tuple) else
        (check_number,)
    )
    for issue in volume_issues:
        if issue['calculated_issue_number'] in numbers:
            number_found += 1

    return number_found == len(numbers)


def _match_special_version(
    reference_version: Union[SpecialVersion, str, None],
    check_version: Union[SpecialVersion, str, None],
    issue_number: Union[Tuple[float, float], float, None] = None
) -> bool:
    """Check if Special Version's match. Takes into consideration that files
    have lacking state specificity.

    Args:
        reference_version (Union[SpecialVersion, str, None]): The state to check
        against.

        check_version (Union[SpecialVersion, str, None]): The state to check.

        issue_number (Union[Tuple[float, float], float, None], optional): The
        issue number to check for if applicable. E.g. so that issue_number == 1
        and special_version == 'one-shot' | 'hard-cover' will match.
            Defaults to None.

    Returns:
        bool: Whether the states match.
    """
    if check_version in (
        reference_version,
        SpecialVersion.COVER,
        SpecialVersion.METADATA
    ):
        return True

    if (
        issue_number == 1.0
        and reference_version in (
            SpecialVersion.HARD_COVER,
            SpecialVersion.ONE_SHOT
        )
    ):
        return True

    if (
        reference_version == SpecialVersion.VOLUME_AS_ISSUE
        and check_version == SpecialVersion.NORMAL
    ):
        return True

    # Volume's Special Version could be one that often isn't explicitly
    # mentioned in the filename or that isn't possible to determine from the
    # filename. EF will determine the file to be a TPB in such scenario.
    return (
        check_version == SpecialVersion.TPB
        and reference_version in (
            SpecialVersion.HARD_COVER,
            SpecialVersion.ONE_SHOT,
            SpecialVersion.VOLUME_AS_ISSUE
        )
    )


def folder_extraction_filter(
    file_data: FilenameData,
    volume_data: VolumeData,
    volume_issues: List[dict],
    end_year: Union[int, None]
) -> bool:
    """The filter applied to the files when extracting from a folder,
    which decides which file is relevant and which one isn't.
    This filter is relatively conservative.

    Args:
        file_data (FilenameData): Extracted data from file.
        volume_data (VolumeData): The data of the volume.
        volume_issues (List[dict]): The data of the issues of the volume.
        end_year (Union[int, None]): Year of last issue or volume year.

    Returns:
        bool: Whether the file passes the filter (if it should be kept or not).
    """
    annual = 'annual' in volume_data.title.lower()

    matching_title = _match_title(
        file_data['series'],
        volume_data.title
    )

    matching_year = _match_year(
        volume_data.year,
        file_data['year'],
        end_year
    )

    matching_volume_number = _match_volume_number(
        volume_data,
        volume_issues,
        file_data['volume_number'],
    )

    # Neither are found (we play it safe so we keep those)
    neither_found = (
        file_data['year'], file_data['volume_number']
    ) == (None, None)

    return (
        matching_title
        and file_data['annual'] == annual
        and (
            matching_year
            or matching_volume_number
            or neither_found
        )
    )


def file_importing_filter(
    file_data: FilenameData,
    volume_data: VolumeData,
    volume_issues: List[dict],
    number_to_year: Mapping[float, Union[int, None]]
) -> bool:
    """Filter for matching files to volumes.

    Args:
        file_data (FilenameData): Extraced data from file.
        volume_data (VolumeData): The data of the volume.
        volume_issues (List[dict]): The data of the issues of the volume.

    Returns:
        bool: Whether the file passes the filter (if it should be matched or not).
    """
    if file_data['issue_number'] is not None:
        issue_number = file_data['issue_number']

    elif (
        volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
        and file_data['volume_number'] is not None
    ):
        issue_number = file_data['volume_number']

    else:
        issue_number = float('-inf')

    matching_special_version = _match_special_version(
        volume_data.special_version,
        file_data['special_version'],
        file_data['issue_number']
    )

    matching_volume_number = _match_volume_number(
        volume_data,
        volume_issues,
        file_data['volume_number']
    )

    matching_year = _match_year(
        volume_data.year,
        file_data['year'],
        number_to_year.get(create_range(issue_number)[-1])
    )

    is_match = (
        matching_special_version
        and (
            matching_volume_number
            or matching_year
        )
    )

    return is_match


def gc_group_filter(
    processed_desc: FilenameData,
    volume_data: VolumeData,
    last_issue_date: str,
    volume_issues: List[dict]
) -> bool:
    """Filter for deciding if a GC download group is a match for the
    volume/issue.

    Args:
        processed_desc (FilenameData): Extracted data from group title.
        volume_data (VolumeData): The data of the volume.
        last_issue_date (str): The date of the last released issue of the volume.
        volume_issues (List[dict]): The data of the issues of the volume.

    Returns:
        bool: Whether the group passes the filter.
    """
    last_year = extract_year_from_date(last_issue_date, volume_data.year)
    annual = 'annual' in volume_data.title.lower()

    matching_title = _match_title(
        volume_data.title,
        processed_desc['series']
    )

    matching_volume_number = _match_volume_number(
        volume_data,
        volume_issues,
        processed_desc['volume_number'],
        conservative=True
    )

    matching_year = _match_year(
        volume_data.year,
        processed_desc['year'],
        last_year,
        conservative=True
    )

    matching_special_version = _match_special_version(
        volume_data.special_version.value,
        processed_desc['special_version'],
        processed_desc['issue_number']
    )

    is_match = (
        matching_title
        and processed_desc['annual'] == annual
        and matching_special_version
        and matching_volume_number
        and matching_year
    )

    return is_match


def check_search_result_match(
    result: SearchResultData,
    volume_data: VolumeData,
    volume_issues: List[dict],
    number_to_year: Mapping[float, Union[int, None]],
    calculated_issue_number: Union[float, None] = None
) -> SearchResultMatchData:
    """Filter for deciding if a search result is a match with what is searched
    for.

    Args:
        result (SearchResultData): A search result.

        volume_data (VolumeData): The data of the volume.

        volume_issues (List[dict]): The data of the issues of the volume.

        number_to_year (Mapping[float, Union[int, None]]):
        calculated_issue_number to release year for all issues of volume.

        calculated_issue_number (Union[float, None], optional): The calculated
        issue number of the issue, if the search was for an issue.
            Defaults to None.

    Returns:
        SearchResultMatchData: Whether the search result passes the filter.
    """
    annual = 'annual' in volume_data.title.lower()

    if blocklist_contains(result['link']):
        return {'match': False, 'match_issue': 'Link is blocklisted'}

    if result['annual'] != annual:
        return {'match': False, 'match_issue': 'Annual conflict'}

    if not (
        _match_title(volume_data.title, result['series'])
        or _match_title(volume_data.alt_title or '', result['series'])
    ):
        return {'match': False, 'match_issue': "Titles don't match"}

    if not _match_volume_number(
        volume_data,
        volume_issues,
        result['volume_number'],
        conservative=True
    ):
        return {'match': False, 'match_issue': "Volume numbers don't match"}

    if not _match_special_version(
        volume_data.special_version,
        result['special_version'],
        result['issue_number']
    ):
        return {'match': False, 'match_issue': 'Special version conflict'}

    if result['issue_number'] is not None:
        issue_number = result['issue_number']

    elif (
        volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
        and result['volume_number'] is not None
    ):
        issue_number = result['volume_number']

    else:
        issue_number = float('-inf')

    if volume_data.special_version in (
        SpecialVersion.NORMAL,
        SpecialVersion.VOLUME_AS_ISSUE
    ):
        if calculated_issue_number is None:
            # Volume search
            if not all(
                i in number_to_year
                for i in create_range(issue_number)
            ):
                # One of the extracted issue numbers is not found in volume
                return {
                    'match': False,
                    'match_issue': "Issue numbers don't match"}

        elif issue_number != calculated_issue_number:
            # Issue search, but
            # extracted issue number(s) don't match number of searched issue
            return {'match': False, 'match_issue': "Issue numbers don't match"}

    if not _match_year(
        volume_data.year,
        result['year'],
        number_to_year.get(create_range(issue_number)[-1]),
        conservative=True
    ):
        return {'match': False, 'match_issue': "Year doesn't match"}

    return {'match': True, 'match_issue': None}
