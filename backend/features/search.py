# -*- coding: utf-8 -*-

from asyncio import gather, run
from typing import Dict, List, Set, Tuple, TypedDict, Union

from backend.base.definitions import (IndexerClient, MatchedSearchResultData,
                                      QueryBuilder, QueryResult,
                                      SearchAction, SearchIterationStats,
                                      SearchQuery, SpecialVersion)
from backend.base.file_extraction import refine_special_version
from backend.base.helpers import (check_overlapping_issues,
                                  extract_year_from_date, force_range)
from backend.base.logging import LOGGER
from backend.implementations.indexer_client_manager import IndexerClients
from backend.implementations.matching import check_search_result_match
from backend.implementations.query_builder_manager import QueryBuilders
from backend.implementations.search_action_planner import SearchActionPlanner
from backend.implementations.volumes import Volume


class IndexerTeam(TypedDict):
    indexer: IndexerClient
    query_builder: QueryBuilder
    search_action_planner: SearchActionPlanner


class SearchCoordinator:
    """
    The Search Coordinator handles searching for downloads from start to
    finish, across all indexers. Initialise a coordinator per volume/issue
    search.
    """

    def __init__(
        self,
        volume_id: int,
        wanted_issues: List[int]
    ) -> None:
        """Initalise the coordinator.

        Args:
            volume_id (int): The ID of the volume to search for.
            wanted_issues (List[int]): The IDs of the issues to search for.
        """
        volume = Volume(volume_id, check_existence=False)
        self.volume_data = volume.get_data()
        self.issue_data = volume.get_issues()
        self.number_to_year: Dict[float, Union[int, None]] = {
            i.calculated_issue_number: extract_year_from_date(i.date)
            for i in self.issue_data
        }

        self.wanted_issues = wanted_issues
        self.found_results: List[MatchedSearchResultData] = []
        self.found_links: Set[str] = set()
        self.is_issue_search = len(self.wanted_issues) == 1

        self.indexers: List[IndexerTeam] = []
        for client in IndexerClients.get_all_clients():
            if not client.get_indexer_data()["enabled"]:
                continue

            self.indexers.append({
                "indexer": client,
                "query_builder": QueryBuilders.get_builder(
                    client.download_type
                )(),
                "search_action_planner": SearchActionPlanner(
                    self.volume_data,
                    self.issue_data,
                    wanted_issues
                )
            })

        return

    def _rank_search_result(
        self,
        result: MatchedSearchResultData,
        issue_year: Union[int, None] = None,
        calculated_issue_number: Union[float, None] = None
    ) -> List[int]:
        """Give a search result a rank, to sort it on.

        Args:
            result (MatchedSearchResultData): A search result.

            issue_year (Union[int, None]], optional): The year of the issue,
                if searching for an issue and release date is known.
                Defaults to None.

            calculated_issue_number (Union[float, None], optional): The
                calculated_issue_number of the issue.
                Defaults to None.

        Returns:
            List[int]: A list of numbers which determines the ranking of the result.
        """
        title = self.volume_data.title
        volume_number = self.volume_data.volume_number
        year = self.volume_data.year

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
            issue_year is not None
            and result['year'] is not None
            and issue_year == result['year']
        ):
            # issue year direct match
            vy_score -= 2

        elif (
            year is not None
            and issue_year is not None
            and result['year'] is not None
            and year - 1 <= result['year'] <= issue_year + 1
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
                rating.append(result["issue_number"])

        return rating

    async def _run_iteration(self) -> List[Tuple[SearchQuery, QueryResult]]:
        """Run one iteration of the searching loop for all indexers.

        Returns:
            List[Tuple[SearchQuery, QueryResult]]: The query and accompanying
                search results from the iteration.
        """
        actions = [
            team["search_action_planner"].next_action()
            for team in self.indexers
        ]

        # Remove indexers that should stop
        for idx, (action, _) in list(enumerate(actions)):
            if action == SearchAction.STOP:
                del actions[idx]
                await self.indexers[idx]["indexer"].shutdown()
                del self.indexers[idx]

        queries = [
            team["query_builder"].next_query(action, query_keys)
            for (action, query_keys), team in zip(actions, self.indexers)
        ]

        result = await gather(*(
            team["indexer"].search(query)
            for query, team in zip(queries, self.indexers)
        ))

        return list(zip(queries, result))

    async def search(self) -> List[MatchedSearchResultData]:
        """Perform the search.

        Returns:
            List[MatchedSearchResultData]: All search results.
        """
        calculated_issue_number = None
        issue_year = None
        if self.is_issue_search and self.indexers:
            issue_data = self.indexers[0][
                "search_action_planner"
            ].issue_data[
                self.wanted_issues[0]
            ]
            calculated_issue_number = issue_data.calculated_issue_number
            issue_year = extract_year_from_date(issue_data.date)

        while self.indexers and self.wanted_issues:
            all_results = await self._run_iteration()

            for (indexer_query, indexer_results), team in zip(
                all_results, self.indexers
            ):
                stats = SearchIterationStats(
                    result_count=len(indexer_results.results),
                    matched_count=0,
                    new_match_count=0,
                    next_page_available=indexer_results.next_page_available,
                    remaining_wanted_issues=self.wanted_issues,
                    total_available_variations=indexer_query[
                        'total_available_variations'
                    ]
                )

                for indexer_result in indexer_results.results:
                    indexer_result = refine_special_version(
                        self.volume_data,
                        indexer_result
                    )

                    is_duplicate = indexer_result["link"] in self.found_links

                    match_result = check_search_result_match(
                        indexer_result, self.volume_data, self.issue_data,
                        self.number_to_year, calculated_issue_number
                    )
                    if match_result['match']:
                        stats.matched_count += 1

                        if is_duplicate:
                            pass

                        elif indexer_result["special_version"]:
                            self.wanted_issues.clear()
                            stats.new_match_count += 1

                        elif (
                            indexer_result["issue_number"] is not None
                        ):
                            n_start, n_end = force_range(
                                indexer_result["issue_number"]
                            )
                            newly_covered_issue = False
                            for issue in self.issue_data:
                                if (
                                    n_start <= issue.calculated_issue_number
                                        <= n_end
                                ):
                                    try:
                                        self.wanted_issues.remove(issue.id)
                                        newly_covered_issue = True
                                    except ValueError:
                                        pass

                            if newly_covered_issue:
                                stats.new_match_count += 1

                    if not is_duplicate:
                        self.found_links.add(indexer_result['link'])
                        self.found_results.append({
                            **indexer_result,
                            **match_result
                        })

                team["search_action_planner"].process_stats(stats)

        await gather(*(
            indexer['indexer'].shutdown()
            for indexer in self.indexers
        ))

        self.found_results.sort(key=lambda r: self._rank_search_result(
            r, issue_year, calculated_issue_number
        ))
        return self.found_results


def manual_search(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
    """Do a manual search for a volume or issue.

    Args:
        volume_id (int): The id of the volume to search for.
        issue_id (Union[int, None], optional): The ID of the issue to search for,
            in the case that you want to search for an issue instead of a volume.
            Defaults to None.

    Returns:
        List[MatchedSearchResultData]: List with search results.
    """
    volume = Volume(volume_id)
    volume_data = volume.get_data()

    if issue_id:
        wanted_issues = [issue_id]
        issue_number = volume.get_issue(issue_id).get_data().issue_number
    else:
        wanted_issues = [
            issue.id
            for issue in volume.get_issues(_skip_files=True)
        ]
        issue_number = None

    LOGGER.info(
        'Starting manual search: %s (%d) %s',
        volume_data.title, volume_data.year,
        f'#{issue_number}' if issue_number else ''
    )

    coordinator = SearchCoordinator(volume_id, wanted_issues)
    results = run(coordinator.search())
    LOGGER.debug('Manual search results: %s', results)
    return results


def auto_search(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
    """Search for a volume or issue and automatically choose a result.

    Args:
        volume_id (int): The ID of the volume to search for.
        issue_id (Union[int, None], optional): The ID of the issue to search for,
            in the case that you want to search for an issue instead of a volume.
            Defaults to None.

    Returns:
        List[MatchedSearchResultData]: List with chosen search results.
    """
    volume = Volume(volume_id)
    volume_data = volume.get_data()
    volume_issues = volume.get_issues(_skip_files=True)
    volume_issues.sort(key=lambda i: i.calculated_issue_number)

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

    coordinator = SearchCoordinator(
        volume_id,
        [i[0] for i in searchable_issues]
    )
    search_results = [
        r
        for r in run(coordinator.search())
        if r["match"]
    ]

    if issue_id is not None or volume_data.special_version not in (
        SpecialVersion.NORMAL,
        SpecialVersion.VOLUME_AS_ISSUE
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
        result = refine_special_version(volume_data, result)

        # Determine what issues the result covers
        if result["special_version"]:
            result["issue_number"] = 1.0
            covered_issues = volume_issues

        elif result["issue_number"] is not None:
            if isinstance(result["issue_number"], tuple):
                n_start, n_end = result["issue_number"]
            else:
                n_start, n_end = force_range(result["issue_number"])

            covered_issues = [
                issue
                for issue in volume_issues
                if n_start <= issue.calculated_issue_number <= n_end
            ]

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
                part["issue_number"], # type: ignore
                result["issue_number"]
            ):
                break
        else:
            chosen_downloads.append(result)

    LOGGER.debug('Auto search results: %s', chosen_downloads)
    return chosen_downloads
