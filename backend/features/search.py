# -*- coding: utf-8 -*-

from asyncio import gather, run
from typing import Dict, List, Tuple, Union

from backend.base.definitions import (MatchedSearchResultData,
                                      SearchResultData, SearchSource,
                                      SpecialVersion, query_formats)
from backend.base.helpers import (AsyncSession, check_overlapping_issues,
                                  create_range, extract_year_from_date,
                                  get_subclasses)
from backend.base.logging import LOGGER
from backend.implementations.getcomics import search_getcomics
from backend.implementations.matching import check_search_result_match
from backend.implementations.volumes import Volume


def _rank_search_result(
    result: MatchedSearchResultData,
    title: str,
    volume_number: int,
    year: Tuple[Union[int, None], Union[int, None]] = (None, None),
    calculated_issue_number: Union[float, None] = None
) -> List[int]:
    """Give a search result a rank, based on which you can sort.

    Args:
        result (MatchedSearchResultData): A search result.

        title (str): Title of volume.

        volume_number (int): The volume number of the volume.

        year (Tuple[Union[int, None], Union[int, None]], optional): The year of
        the volume and the year of the issue if searching for an issue and
        release date is known.
            Defaults to (None, None).

        calculated_issue_number (Union[float, None], optional): The
        calculated_issue_number of the issue.
            Defaults to None.

    Returns:
        List[int]: A list of numbers which determines the ranking of the result.
    """
    rating = []

    # Prefer matches (False == 0 == higher rank)
    rating.append(not result['match'])

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
        # Search was for issue
        if (
            isinstance(result['issue_number'], float)
            and calculated_issue_number == result['issue_number']
        ):
            # Issue number is direct match
            rating.append(0)

        elif isinstance(result['issue_number'], tuple):
            if (
                result['issue_number'][0]
                <= calculated_issue_number
                <= result['issue_number'][1]
            ):
                # Issue number falls between range
                rating.append(
                    1 - (1 / (
                        result['issue_number'][1] - result['issue_number'][0] + 1
                    ))
                )

            else:
                # Issue number falls outside so release is not useful
                rating.append(3)

        elif result['special_version'] is not None:
            # Issue number not found but is special version
            rating.append(2)

        else:
            # No issue number found and not special version
            rating.append(3)

    else:
        # Search was for volume
        if isinstance(result['issue_number'], tuple):
            rating.append(
                1.0
                /
                (result['issue_number'][1] - result['issue_number'][0] + 1)
            )

        elif isinstance(result['issue_number'], float):
            rating.append(1)

    return rating


class SearchGetComics(SearchSource):
    async def search(self, session: AsyncSession) -> List[SearchResultData]:
        return await search_getcomics(session, self.query)


async def search_multiple_queries(*queries: str) -> List[SearchResultData]:
    """Do a manual search for multiple queries asynchronously.

    Returns:
        List[SearchResultData]: The search results for all queries together,
        duplicates removed.
    """
    async with AsyncSession() as session:
        searches = [
            Source(query).search(session)
            for Source in get_subclasses(SearchSource)
            for query in queries
        ]
        responses = await gather(*searches)

    search_results: List[SearchResultData] = []
    processed_links = set()
    for response in responses:
        for result in response:
            # Don't add if the link is already in the results
            # Avoids duplicates, as multiple formats can return the same result
            if result['link'] not in processed_links:
                search_results.append(result)
                processed_links.add(result['link'])

    return search_results


def manual_search(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
    """Do a manual search for a volume or issue.

    Args:
        volume_id (int): The id of the volume to search for.
        issue_id (Union[int, None], optional): The id of the issue to search for,
        in the case that you want to search for an issue instead of a volume.
            Defaults to None.

    Returns:
        List[MatchedSearchResultData]: List with search results.
    """
    volume = Volume(volume_id)
    volume_data = volume.get_data()
    volume_issues = volume.get_issues()
    number_to_year: Dict[float, Union[int, None]] = {
        i.calculated_issue_number: extract_year_from_date(i.date)
        for i in volume_issues
    }
    issue_number: Union[str, None] = None
    calculated_issue_number: Union[float, None] = None

    if issue_id and volume_data.special_version in (
        SpecialVersion.NORMAL,
        SpecialVersion.VOLUME_AS_ISSUE
    ):
        issue_data = volume.get_issue(issue_id).get_data()
        issue_number = issue_data.issue_number
        calculated_issue_number = issue_data.calculated_issue_number

    LOGGER.info(
        'Starting manual search: %s (%d) %s',
        volume_data.title, volume_data.year,
        f'#{issue_number}' if issue_number else ''
    )

    for title in (volume_data.title, volume_data.alt_title):
        if not title:
            continue

        if volume_data.special_version == SpecialVersion.TPB:
            formats = query_formats["TPB"]

        elif volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE:
            formats = query_formats["VAI"]

        elif issue_number is None:
            formats = query_formats["Volume"]

        else:
            formats = query_formats["Issue"]

        if volume_data.year is None:
            formats = tuple(
                f.replace('({year})', '').strip()
                for f in formats
            )

        search_title = title.replace(':', '')
        search_results = run(search_multiple_queries(*(
            format.format(
                title=search_title, volume_number=volume_data.volume_number,
                year=volume_data.year, issue_number=issue_number
            )
            for format in formats
        )))
        if not search_results:
            continue

        results: List[MatchedSearchResultData] = [
            {
                **result,
                **check_search_result_match(
                    result, volume_data, volume_issues,
                    number_to_year, calculated_issue_number
                )
            }
            for result in search_results
        ]

        # Sort results; put best result at top
        results.sort(key=lambda r: _rank_search_result(
            r, search_title, volume_data.volume_number,
            (
                volume_data.year,
                number_to_year.get(calculated_issue_number) # type: ignore
            ),
            calculated_issue_number
        ))

        LOGGER.debug('Manual search results: %s', results)
        return results

    return []


def auto_search(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
    """Search for a volume or issue and automatically choose a result.

    Args:
        volume_id (int): The ID of the volume to search for.
        issue_id (Union[int, None], optional): The id of the issue to search for,
        in the case that you want to search for an issue instead of a volume.
            Defaults to None.

    Returns:
        List[MatchedSearchResultData]: List with chosen search results.
    """
    volume = Volume(volume_id)
    volume_data = volume.get_data()
    special_version = volume_data.special_version
    LOGGER.info(
        'Starting auto search for volume %d %s',
        volume_id,
        f'issue {issue_id}' if issue_id else ''
    )

    searchable_issues: List[Tuple[int, float]] = []
    if not volume_data.monitored:
        # Volume is unmonitored so don't auto search
        pass

    elif issue_id is None:
        # Auto search volume
        # Get open issues (monitored and no file).
        searchable_issues = volume.get_open_issues()

    else:
        # Auto search issue
        issue = volume.get_issue(issue_id)
        issue_data = issue.get_data()
        if issue_data.monitored and not issue.get_files():
            # Issue is open
            searchable_issues = [(issue_id, issue_data.calculated_issue_number)]

    if not searchable_issues:
        # No issues to search for
        result = []
        LOGGER.debug(f'Auto search results: {result}')
        return result

    search_results = [
        r
        for r in manual_search(volume_id, issue_id)
        if r['match']
    ]

    if issue_id is not None or (
        special_version.value is not None
        and special_version != SpecialVersion.VOLUME_AS_ISSUE
    ):
        # We're searching for one "item", so just grab first search result.
        result = search_results[:1] if search_results else []
        LOGGER.debug('Auto search results: %s', result)
        return result

    # We're searching for a volume, so we might download multiple search results.
    # Find a combination of search results that download the most issues.
    chosen_downloads: List[MatchedSearchResultData] = []
    searchable_issue_numbers = {i[1] for i in searchable_issues}
    for result in search_results:
        # Determine what issues the result covers
        if result['issue_number'] is not None:
            # Normal issue, VAS with issue number,
            # OS/HC using issue 1
            result['_issue_number'] = result['issue_number']
            covered_issues = volume.get_issues_in_range(
                *create_range(result['issue_number'])
            )

        elif (
            special_version == SpecialVersion.VOLUME_AS_ISSUE
            and result['special_version'] == SpecialVersion.TPB
        ):
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

            covered_issues = volume.get_issues_in_range(
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
            covered_issues = volume.get_issues()

        else:
            continue

        if any(
            i.calculated_issue_number not in searchable_issue_numbers
            for i in covered_issues
        ):
            # Part or all of what the result covers is already downloaded
            continue

        # Check that any other selected download doesn't already cover the issue
        for part in chosen_downloads:
            if check_overlapping_issues(
                part.get('_issue_number', 0.0),
                result['_issue_number']
            ):
                break
        else:
            chosen_downloads.append(result)

    # Find issues that have still not been covered. Might've been that the
    # download for the issue simply did not pop up on volume search, but will
    # when searching for the individual issue.
    missing_issues = [
        i
        for i in searchable_issues
        if not any(
            check_overlapping_issues(
                i[1], part.get('_issue_number', 0.0)
            )
            for part in chosen_downloads
        )
    ]

    for missing_issue in missing_issues:
        chosen_downloads.extend(auto_search(volume_id, missing_issue[0]))

    LOGGER.debug('Auto search results: %s', chosen_downloads)
    return chosen_downloads
