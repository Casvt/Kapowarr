# -*- coding: utf-8 -*-

from asyncio import gather, run
from datetime import datetime, timedelta
from time import time
from typing import Dict, List

from backend.base.definitions import SearchResultData
from backend.base.file_extraction import refine_special_version
from backend.base.helpers import extract_year_from_date
from backend.base.logging import LOGGER
from backend.features.search_full import choose_downloads
from backend.implementations.indexer_client_manager import IndexerClients
from backend.implementations.matching import (check_search_result_match,
                                              match_title)
from backend.implementations.volumes import Volume
from backend.internals.db import get_db
from backend.internals.settings import Settings


async def _get_all_new_releases() -> List[SearchResultData]:
    """Get all downloads released since the last RSS sync.

    Returns:
        List[SearchResultData]: The list of downloads.
    """
    indexers = [
        indexer
        for indexer in IndexerClients.get_all_clients()
        if indexer.get_indexer_data()["enabled"]
    ]

    last_rss_sync = (
        datetime.fromtimestamp(Settings().sv.last_rss_sync)
        - timedelta(days=2)
    )

    results = await gather(*(
        indexer.discover(last_rss_sync)
        for indexer in indexers
    ))

    await gather(*(
        indexer.shutdown()
        for indexer in indexers
    ))

    return [
        download
        for result in results
        for download in result
    ]


def discover_downloads() -> Dict[int, List[SearchResultData]]:
    """Perform an RSS sync (a.k.a. download discovery).

    Returns:
        Dict[int, List[SearchResultData]]: A mapping from volume ID to results
            for that volume that can be downloaded.
    """
    all_releases = run(_get_all_new_releases())

    cursor = get_db()
    cursor.execute(
        "SELECT id, title, alt_title FROM volumes WHERE monitored = 1;"
    )

    # Match releases to volumes purely based on title, as a first filter
    title_matches: Dict[int, List[SearchResultData]] = {}
    for v_id, title, alt_title in cursor:
        for release in all_releases:
            if (
                match_title(title, release["series"])
                or match_title(alt_title or '', release["series"])
            ):
                title_matches.setdefault(v_id, []).append(release)

    full_matches: Dict[int, List[SearchResultData]] = {}
    for volume_id, releases in title_matches.items():
        volume = Volume(volume_id)
        volume_data = volume.get_data()
        issue_data = volume.get_issues(_skip_files=True)
        issue_data.sort(key=lambda i: i.calculated_issue_number)
        number_to_year = {
            i.calculated_issue_number: extract_year_from_date(i.date)
            for i in issue_data
        }

        matched_releases: List[SearchResultData] = []
        for release in releases:
            release = refine_special_version(
                volume_data, release
            )
            match_result = check_search_result_match(
                release, volume_data, issue_data, number_to_year, None
            )
            if match_result["match"]:
                matched_releases.append(release)

        full_matches[volume_id] = choose_downloads(
            matched_releases, volume.get_open_issues(), issue_data
        )

    LOGGER.debug('Matching releases from RSS Sync: %s', full_matches)

    Settings().update({"last_rss_sync": round(time())})
    return full_matches
