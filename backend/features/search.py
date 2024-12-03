# -*- coding: utf-8 -*-

"""
Searching online sources (GC) for downloads
"""

from asyncio import create_task, gather, run
from typing import Dict, List, Tuple, Union

from backend.base.definitions import (MatchedSearchResultData,
                                      SearchResultData, SpecialVersion)
from backend.base.helpers import (AsyncSession, check_overlapping_issues,
                                  create_range, extract_year_from_date,
                                  first_of_column)
from backend.base.logging import LOGGER
from backend.implementations.getcomics import search_getcomics
from backend.implementations.matching import (_match_special_version,
                                              check_search_result_match)
from backend.implementations.volumes import (Issue, Volume,
                                             get_calc_number_range)
from backend.internals.db import get_db


def _sort_search_results(
    result: MatchedSearchResultData,
    title: str,
    volume_number: int,
    year: Tuple[Union[int, None], Union[int, None]] = (None, None),
    calculated_issue_number: Union[float, None] = None
) -> List[int]:
    """Sort the search results

    Args:
        result (MatchedSearchResultData): A result from `search.SearchSources.search_all()`.

        title (str): Title of volume

        volume_number (int): The volume number of the volume

        year (Tuple[Union[int, None], Union[int, None]], optional): The year of
        the volume and the issue.
            Defaults to (None, None).

        calculated_issue_number (Union[float, None], optional): The
        calculated_issue_number of the issue.
            Defaults to None.

    Returns:
        List[int]: A list of numbers which determines the ranking of the result.
    """
    rating = []

    # Prefer matches
    rating.append(int(not result['match']))

    # The more words in the search term that are present in
    # the search results' title, the higher ranked it gets
    split_title = title.split(' ')
    rating.append(len([
        word
        for word in result['series'].split(' ')
        if word not in split_title
    ]))

    # Prefer volume number or year matches, even better if both match
    vy_score = 3
    if (
        result['volume_number'] is not None
        and result['volume_number'] == volume_number
    ):
        vy_score -= 1

    if (
        year[1] is not None
        and result['year'] is not None
        and year[1] == result['year']
    ):
        # issue year direct match
        vy_score -= 2

    elif (
        year[0] is not None
        and year[1] is not None
        and result['year'] is not None
        and year[0] - 1 <= result['year'] <= year[1] + 1
    ):
        # fuzzy match between start year and issue year
        vy_score -= 1

    rating.append(vy_score)

    # Sort on issue number fitting
    if calculated_issue_number is not None:
        if (isinstance(result['issue_number'], float)
        and calculated_issue_number == result['issue_number']):
            # Issue number is direct match
            rating.append(0)

        elif isinstance(result['issue_number'], tuple):
            if result['issue_number'][0] <= calculated_issue_number <= result['issue_number'][1]:
                # Issue number falls between range
                rating.append(
                    1 - (1
                        /
                        (result['issue_number'][1] - result['issue_number'][0] + 1))
                )
            else:
                # Issue number falls outside so release is not usefull
                rating.append(3)

        elif (result['issue_number'] is None
        and result['special_version'] is not None):
            # Issue number not found but is special version
            rating.append(2)

        else:
            rating.append(3)
    else:
        if isinstance(result['issue_number'], tuple):
            rating.append(
                1.0
                /
                (result['issue_number'][1] - result['issue_number'][0] + 1)
            )

        elif isinstance(result['issue_number'], float):
            rating.append(1)

    return rating


class SearchSources:
    "For getting search results from various sources"

    def __init__(self, query: str):
        """Prepare a search

        Args:
            query (str): The search string to search for in the sources
        """
        self.query = query
        self.source_list = [
            self._get_comics,
        ]

    async def search_all(self) -> List[SearchResultData]:
        "Search all sources for the query"
        result: List[SearchResultData] = []

        async with AsyncSession() as session:
            tasks = [
                create_task(source(session))
                for source in self.source_list
            ]
            responses = await gather(*tasks)

        for r in responses:
            result += r

        return result

    async def _get_comics(
        self,
        session: AsyncSession
    ) -> List[SearchResultData]:
        """Search for the query in getcomics

        Returns:
            List[SearchResultData]: The search results.
        """
        return await search_getcomics(session, self.query)


async def search_multiple_queries(*queries: str) -> List[SearchResultData]:
    """Do a manual search for multiple queries asynchronously.

    Returns:
        List[SearchResultData]: The search results for all queries together,
        duplicates removed.
    """
    search_results: List[SearchResultData] = []
    format_searches = [
        SearchSources(q)
        for q in queries
    ]
    tasks = [
        create_task(ss.search_all())
        for ss in format_searches
    ]
    responses = await gather(*tasks)
    for r in responses:
        search_results += r

    # Remove duplicates
    # because multiple formats can return the same result
    search_results = list({r['link']: r for r in search_results}.values())

    return search_results


def manual_search(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
    """Do a manual search for a volume or issue

    Args:
        volume_id (int): The id of the volume to search for
        issue_id (Union[int, None], optional): The id of the issue to search for
        (in the case that you want to search for an issue instead of a volume).
        Defaults to None.

    Returns:
        List[MatchedSearchResultData]: List with search results.
    """
    volume = Volume(volume_id)
    volume_data = volume.get_keys(
        ('title', 'alt_title', 'volume_number', 'year', 'special_version')
    )

    if issue_id and not volume_data.special_version.value:
        issue_data = Issue(issue_id).get_keys(
            ('issue_number', 'calculated_issue_number')
        )
        issue_number: Union[str, None] = issue_data['issue_number']
        calculated_issue_number: Union[float, None] = issue_data[
            'calculated_issue_number'
        ]

    else:
        issue_number: Union[str, None] = None
        calculated_issue_number: Union[float, None] = None

    LOGGER.info(
        f'Starting manual search: {volume_data.title} ({volume_data.year}) {"#" + issue_number if issue_number else ""}'
    )

    # Prepare query
    results = []
    for search_title in (volume_data.title, volume_data.alt_title):
        if search_title is None:
            continue
        title = search_title.replace(':', '')

        if volume_data.special_version == SpecialVersion.TPB:
            query_formats = (
                '{title} Vol. {volume_number} ({year}) TPB',
                '{title} ({year}) TPB',
                '{title} Vol. {volume_number} TPB',
                '{title} Vol. {volume_number}',
                '{title}'
            )
        elif volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE:
            query_formats = (
                '{title} ({year})',
                '{title}'
            )
        elif issue_number is None:
            query_formats = (
                '{title} Vol. {volume_number} ({year})',
                '{title} ({year})',
                '{title} Vol. {volume_number}',
                '{title}'
            )
        else:
            query_formats = (
                '{title} #{issue_number} ({year})',
                '{title} Vol. {volume_number} #{issue_number}',
                '{title} #{issue_number}',
                '{title}'
            )

        if volume_data.year is None:
            query_formats = tuple(
                f.replace('({year})', '')
                for f in query_formats
            )

        search_results = run(search_multiple_queries(*(
            format.format(
                title=title, volume_number=volume_data.volume_number,
                year=volume_data.year, issue_number=issue_number
            )
            for format in query_formats
        )))
        if not search_results:
            continue

        # Decide what is a match and what not
        volume_issues = volume.get_issues()
        number_to_year: Dict[float, Union[int, None]] = {
            i['calculated_issue_number']: extract_year_from_date(i['date'])
            for i in volume_issues
        }
        results = [
            MatchedSearchResultData({
                **result,
                **check_search_result_match(
                    result, volume_data, volume_issues,
                    number_to_year, calculated_issue_number
                )
            })
            for result in search_results
        ]

        # Sort results; put best result at top
        results.sort(key=lambda r: _sort_search_results(
            r, title, volume_data.volume_number,
            (volume_data.year, number_to_year.get(
                calculated_issue_number)), # type: ignore
            calculated_issue_number
        ))

        break

    LOGGER.debug(f'Manual search results: {results}')
    return results


def auto_search(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
    """Search for a volume or issue and automatically choose a result

    Args:
        volume_id (int): The id of the volume to search for
        issue_id (Union[int, None], optional): The id of the issue to search for
        (in the case that you want to search for an issue instead of a volume).
        Defaults to None.

    Returns:
        List[MatchedSearchResultData]: List with chosen search results.
    """
    cursor = get_db()

    volume = Volume(volume_id)
    monitored = volume['monitored']
    special_version = volume['special_version']
    LOGGER.info(
        f'Starting auto search for volume {volume_id} {f"issue {issue_id}" if issue_id else ""}'
    )
    if not monitored:
        # Volume is unmonitored so regardless of what to search for, ignore
        # searching
        result = []
        LOGGER.debug(f'Auto search results: {result}')
        return result

    searchable_issues: List[float] = []
    if issue_id is None:
        # Auto search volume
        # Get issue numbers that are open (monitored and no file)
        searchable_issues: List[float] = first_of_column(cursor.execute(
            """
            SELECT calculated_issue_number
            FROM issues i
            LEFT JOIN issues_files if
            ON i.id = if.issue_id
            WHERE
                file_id IS NULL
                AND volume_id = ?
                AND monitored = 1;
            """,
            (volume_id,)
        ))
        if not searchable_issues:
            result = []
            LOGGER.debug(f'Auto search results: {result}')
            return result

    else:
        # Auto search issue
        issue = Issue(issue_id)
        if not issue['monitored']:
            # Auto search for issue but issue is unmonitored
            result = []
            LOGGER.debug(f'Auto search results: {result}')
            return result
        else:
            if issue.get_files():
                # Auto search for issue but issue already has file
                result = []
                LOGGER.debug(f'Auto search results: {result}')
                return result

    results = [r for r in manual_search(volume_id, issue_id) if r['match']]

    if issue_id is not None or (
        special_version.value is not None
        and special_version != SpecialVersion.VOLUME_AS_ISSUE
    ):
        result = results[:1] if results else []
        LOGGER.debug(f'Auto search results: {result}')
        return result

    volume_parts = []
    for result in results:
        if not _match_special_version(
                special_version,
                result['special_version'],
                result['issue_number']
        ):
            continue

        if result['issue_number'] is not None:
            # Normal issue, VAS with issue number,
            # OS/HC using issue 1
            result['_issue_number'] = result['issue_number']
            covered_issues = get_calc_number_range(
                volume_id,
                *create_range(result['issue_number'])
            )

        elif (special_version == SpecialVersion.VOLUME_AS_ISSUE
        and result['special_version'] == SpecialVersion.TPB):
            # VAS with volume number
            if result['volume_number'] is None:
                continue

            if isinstance(result['volume_number'], tuple):
                result['_issue_number'] = (
                    float(result['volume_number'][0]),
                    float(result['volume_number'][1])
                )
            else:
                result['_issue_number'] = float(result['volume_number'])

            covered_issues = get_calc_number_range(
                volume_id,
                *create_range(result['volume_number'])
            )

        elif (
            special_version in (
                SpecialVersion.ONE_SHOT,
                SpecialVersion.HARD_COVER,
                SpecialVersion.TPB
            )
            and result['special_version'] in (
                special_version,
                SpecialVersion.TPB
            )
        ):
            # OS/HC using no issue number, TPB
            result['_issue_number'] = 1.0
            covered_issues = (1.0,)

        else:
            continue

        if any(i not in searchable_issues for i in covered_issues):
            continue

        # Check that any other selected download doesn't already cover the issue
        for part in volume_parts:
            if check_overlapping_issues(
                part['_issue_number'],
                result['_issue_number']
            ):
                break
        else:
            volume_parts.append(result)

    LOGGER.debug(f'Auto search results: {volume_parts}')
    return volume_parts
