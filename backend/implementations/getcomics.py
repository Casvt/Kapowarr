# -*- coding: utf-8 -*-

"""
Getting downloads from a GC page
"""

from asyncio import gather
from functools import reduce
from hashlib import sha1
from re import IGNORECASE, compile
from typing import Callable, List, Tuple, Type, Union

from aiohttp import ClientError
from bencoding import bencode
from bs4 import BeautifulSoup, Tag

from backend.base.custom_exceptions import (DownloadLimitReached, FailedGCPage,
                                            IssueNotFound, LinkBroken)
from backend.base.definitions import (BlocklistReason, Constants, Download,
                                      DownloadGroup, FailReason,
                                      GCDownloadSource, SearchResultData,
                                      SpecialVersion, download_source_versions)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import (AsyncSession, check_overlapping_issues,
                                  create_range, fix_year,
                                  get_torrent_info, normalize_year)
from backend.base.logging import LOGGER
from backend.implementations.blocklist import (add_to_blocklist,
                                               blocklist_contains)
from backend.implementations.download_clients import (DirectDownload,
                                                      MediaFireDownload,
                                                      MediaFireFolderDownload,
                                                      MegaDownload,
                                                      MegaFolderDownload,
                                                      PixelDrainDownload,
                                                      PixelDrainFolderDownload,
                                                      TorrentDownload,
                                                      WeTransferDownload)
from backend.implementations.external_clients import ExternalClients
from backend.implementations.flaresolverr import FlareSolverr
from backend.implementations.matching import gc_group_filter
from backend.implementations.volumes import Volume
from backend.internals.db import iter_commit
from backend.internals.settings import Settings

mediafire_dd_regex = compile(
    r'https?://download\d+\.mediafire\.com/',
    IGNORECASE
)


# region Scraping
def _get_max_page(
    soup: BeautifulSoup
) -> int:
    """From a GC search result page, extract the total page count.

    Args:
        soup (BeautifulSoup): The soup of the GC search result page.

    Returns:
        int: The number of pages. E.g. `10` means 10 pages of search results.
    """
    page_links = soup.find_all(["a", "span"], {"class": "page-numbers"})

    if not page_links:
        return 1

    return int(
        page_links[-1]
        .get_text(strip=True)
        .replace(',', '')
        .replace('.', '')
    )


def _get_articles(
    soup: BeautifulSoup
) -> List[Tuple[str, str]]:
    """From a GC search result page, extract article (single search result)
    data.

    Args:
        soup (BeautifulSoup): The soup of the GC search result page.

    Returns:
        List[Tuple[str, str]]: The data of the articles. First string of the
        tuple is the link, second string is the title.
    """
    result: List[Tuple[str, str]] = []
    for article in soup.find_all("article", {"class": "post"}):
        link = create_range(
            article.find('a')["href"] or ''
        )[0]
        title = (
            article
            .find("h1", {"class": "post-title"})
            .get_text(strip=True)
        )
        result.append((link, title))

    return result


def _get_title(
    soup: BeautifulSoup
) -> Union[str, None]:
    """From a GC article, extract the title of the article.

    Args:
        soup (BeautifulSoup): The soup of the GC article.

    Returns:
        Union[str, None]: The title of the article, or `None` if not found.
    """
    title_el = soup.find("h1")
    if not title_el:
        return None
    return title_el.text


def __check_download_link(
    link_text: str,
    link: str,
    torrent_client_available: bool
) -> Union[GCDownloadSource, None]:
    """Check if download link is supported and allowed.

    Args:
        link_text (str): The title of the link.
        link (str): The link itself.
        torrent_client_available (bool): Whether a torrent client is available.

    Returns:
        Union[GCDownloadSource, None]: Either the GC service that the button
        is for or `None` if it's not allowed/unknown.
    """
    LOGGER.debug(f'Checking download link: {link}, {link_text}')
    if not link:
        return

    # Check if link is in blocklist
    if blocklist_contains(link):
        return

    # Check if link is from a service that should be avoided
    if link.startswith('https://sh.st/'):
        return

    # Check if link is from supported source
    for source, versions in download_source_versions.items():
        if any(s in link_text for s in versions):
            LOGGER.debug(
                f'Checking download link: {link_text} maps to {source.value}'
            )

            if 'torrent' in source.value and not torrent_client_available:
                return

            return source

    return


__link_filter_1: Callable[[Tag], bool] = lambda e: (
    e.name == 'p'
    and 'Language' in e.text
    and e.find('p') is None
)


def __extract_button_links(
    body: Tag,
    torrent_client_available: bool
) -> List[DownloadGroup]:
    """Extract download groups that are a list of big buttons.

    Args:
        body (Tag): The body to extract from.
        torrent_client_available (bool): Whether a client is available.

    Returns:
        List[DownloadGroup]: The download groups.
    """
    download_groups: List[DownloadGroup] = []
    for group in body.find_all(__link_filter_1):
        group: Tag
        if not group.next_sibling:
            continue

        # Process data about group
        extracted_title = group.get_text('\x00')
        title = extracted_title.partition('\x00')[0]
        processed_title = extract_filename_data(
            title,
            assume_volume_number=False,
            fix_year=True
        )

        if processed_title['special_version'] == 'cover':
            continue

        if (
            processed_title["year"] is None
            and "Year :\x00\xa0" in extracted_title
        ):
            year = normalize_year(
                extracted_title
                .split("Year :\x00\xa0")[1]
                .split(" |")[0]
                .split('-')[0]
            )
            if year:
                processed_title["year"] = fix_year(year)

        result: DownloadGroup = {
            "web_sub_title": title,
            "info": processed_title,
            "links": {}
        }

        # Extract links from group
        first_find = True
        for e in group.next_sibling.next_elements: # type: ignore
            e: Tag
            if e.name == 'hr':
                break

            elif (
                e.name == 'div'
                and 'aio-button-center' in (e.attrs.get('class', []))
            ):
                group_link: Union[Tag, None] = e.find('a') # type: ignore
                if not group_link:
                    continue
                link_title = group_link.text.strip().lower()
                if group_link.get('href') is None:
                    continue
                href = create_range(group_link.get('href') or '')[0]
                if not href:
                    continue

                match = __check_download_link(
                    link_title,
                    href,
                    torrent_client_available
                )
                if match:
                    if first_find:
                        download_groups.append(result)
                        first_find = False

                    result['links'].setdefault(match, []).append(href)

    return download_groups


__link_filter_2: Callable[[Tag], bool] = lambda e: (
    e.name == 'li'
    and e.parent is not None
    and e.parent.name == 'ul'
    and e.find('a') is not None
)


def __extract_list_links(
    body: Tag,
    torrent_client_available: bool
) -> List[DownloadGroup]:
    """Extract download groups that are in an unsorted list.

    Args:
        body (Tag): The body to extract from.
        torrent_client_available (bool): Whether a client is available.

    Returns:
        List[DownloadGroup]: The download groups.
    """
    download_groups: List[DownloadGroup] = []
    for group in body.find_all(__link_filter_2):
        # Process data about group
        title: str = group.get_text('\x00').partition('\x00')[0]
        processed_title = extract_filename_data(
            title,
            assume_volume_number=False,
            fix_year=True
        )

        if processed_title['special_version'] == 'cover':
            continue

        result: DownloadGroup = {
            "web_sub_title": title,
            "info": processed_title,
            "links": {}
        }

        # Extract links from group
        first_find = True
        for group_link in group.find_all('a'):
            group_link: Tag
            if group_link.get('href') is None:
                continue
            link_title = group_link.text.strip().lower()
            href = create_range(group_link.get('href') or '')[0]
            if not href:
                continue

            match = __check_download_link(
                link_title,
                href,
                torrent_client_available
            )
            if match:
                if first_find:
                    download_groups.append(result)
                    first_find = False

                result['links'].setdefault(match, []).append(href)

    return download_groups


def _get_download_groups(
    soup: BeautifulSoup
) -> List[DownloadGroup]:
    """From a GC article, extract the download groups.

    Args:
        soup (BeautifulSoup): The soup of the GC article.

    Returns:
        List[DownloadGroup]: The download groups.
    """
    LOGGER.debug('Extracting download groups')

    torrent_client_available = bool(ExternalClients.get_clients())

    body: Union[Tag, None] = soup.find(
        'section', {'class': 'post-contents'}
    ) # type: ignore
    if not body:
        return []

    download_groups = __extract_button_links(body, torrent_client_available)
    download_groups.extend(__extract_list_links(body, torrent_client_available))

    service_preference = Settings().sv.service_preference
    for group in download_groups:
        group["links"] = {
            k: v
            for k, v in sorted(
                group["links"].items(),
                key=lambda k: service_preference.index(k[0].value)
            )
        }

    LOGGER.debug(f'Download groups: {download_groups}')
    return download_groups


# region Group Handling
def __sort_link_paths(p: List[DownloadGroup]) -> Tuple[float, int]:
    """Sort the link paths. SV's are sorted highest, then from largest range to
    least, then from least downloads to most for equal range.

    Args:
        p (List[DownloadGroup]): A link path.

    Returns:
        Tuple[float, int]: The rating (lower is better).
    """
    if p[0]['info']['special_version']:
        return (0.0, 0)

    issues_covered = sum(
        reduce(
            lambda a, b: (b - a) or 1,
            create_range(entry["info"]["issue_number"])
        )
        for entry in p
        if entry["info"]["issue_number"] is not None
    )

    return (1 / issues_covered, len(p))


def _create_link_paths(
    download_groups: List[DownloadGroup],
    volume_id: int,
    force_match: bool = False
) -> List[List[DownloadGroup]]:
    """
    Based on the download groups, find different "paths" to download
    the most amount of content without overlapping. E.g. on the same page, there
    might be a download for `TPB + Extra's`, `TPB`, `Issue A-B` and for
    `Issue C-D`. A path would be created for `TPB + Extra's`. A second path
    would be created for `TPB` and a third path for `Issue A-B` + `Issue C-D`.
    Paths 2 and on are basically backup options for if path 1 doesn't work, to
    still get the most content out of the page.

    Args:
        download_groups (List[DownloadGroup]): The download groups.

        volume_id (int): The id of the volume.

        force_match (bool, optional): Don't filter the download groups for
        the volume, but instead just download all content from the page.
            Defaults to False.

    Returns:
        List[List[DownloadGroup]]: The list contains all paths. Each path is
        a list of download groups that don't overlap.
    """
    LOGGER.debug('Creating link paths')

    # Get info of volume
    volume = Volume(volume_id)
    volume_data = volume.get_data()
    ending_year = volume.get_ending_year()
    volume_issues = volume.get_issues()

    link_paths: List[List[DownloadGroup]] = []
    if force_match:
        link_paths.append([])

    for group in download_groups:
        if not (force_match or gc_group_filter(
            group['info'],
            volume_data,
            ending_year,
            volume_issues
        )):
            continue

        # Group matches/contains what is desired to be downloaded
        if (
            volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
            and (
                group["info"]['special_version'] == SpecialVersion.TPB
                or isinstance(group["info"]['volume_number'], tuple)
            )
        ):
            group["info"]["issue_number"] = group["info"]["volume_number"]
            group["info"]["volume_number"] = volume_data.volume_number
            group["info"]["special_version"] = SpecialVersion.VOLUME_AS_ISSUE.value

        if (
            group["info"]['special_version'] is not None
            and group["info"]['special_version']
                != SpecialVersion.VOLUME_AS_ISSUE
            and volume_data.special_version in (
                SpecialVersion.HARD_COVER,
                SpecialVersion.ONE_SHOT
            )
        ):
            group["info"]['special_version'] = volume_data.special_version.value

        if force_match:
            # Add all to the same group
            link_paths[0].append(group)

        elif (
            group["info"]['special_version'] is not None
            and group["info"]['special_version']
            != SpecialVersion.VOLUME_AS_ISSUE
        ):
            link_paths.append([group])

        else:
            # Find path with ranges and single issues that doesn't have
            # a link that already covers this one
            for path in link_paths:
                for entry in path:
                    if entry["info"]["special_version"] not in (
                        SpecialVersion.NORMAL,
                        SpecialVersion.VOLUME_AS_ISSUE
                    ):
                        break

                    elif check_overlapping_issues(
                        entry["info"]["issue_number"], # type: ignore
                        group["info"]["issue_number"] # type: ignore
                    ):
                        break

                else:
                    # No conflicts found so add to path
                    path.append(group)
                    break
            else:
                # Conflict in all paths found so start a new one
                link_paths.append([group])

    link_paths.sort(key=__sort_link_paths)

    LOGGER.debug(f'Link paths: {link_paths}')
    return link_paths


async def __purify_link(
    source: GCDownloadSource,
    link: str
) -> Tuple[str, Type[Download]]:
    """Extract the link that directly leads to the download from the link
    in the GC article.

    Args:
        source (GCDownloadSource): The service that the link is of.
        link (str): The link in the GC article.

    Raises:
        LinkBroken: Link is invalid, not supported or broken.

    Returns:
        Tuple[str, Type[Download]]: The pure link, and the download class for
        the correct service.
    """
    LOGGER.debug(f'Purifying link: {link}')
    if (
        source == GCDownloadSource.GETCOMICS_TORRENT
        and link.startswith("magnet:?")
    ):
        # Direct magnet link
        return link, TorrentDownload

    if not link.startswith("http"):
        raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)

    async with AsyncSession() as session:
        r = await session.get(link)
    if not r.ok:
        raise LinkBroken(BlocklistReason.LINK_BROKEN)
    url = str(r.real_url)
    content_type = r.headers.getone("Content-Type", "")

    if source == GCDownloadSource.MEGA:
        if "#F!" in url or "/folder/" in url:
            # Folder download
            return url, MegaFolderDownload

        # Normal file download
        return url, MegaDownload

    elif source == GCDownloadSource.MEDIAFIRE:
        if 'error.php' in url:
            # Link is broken
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        elif '/folder/' in url:
            # Folder download
            return url, MediaFireFolderDownload

        elif mediafire_dd_regex.search(url):
            # Link on page was to pure link
            return url, DirectDownload

        # Normal file download
        return url, MediaFireDownload

    elif source == GCDownloadSource.WETRANSFER:
        return url, WeTransferDownload

    elif source == GCDownloadSource.PIXELDRAIN:
        if '/l/' in url:
            # Folder download
            return url, PixelDrainFolderDownload

        # File download
        return url, PixelDrainDownload

    elif (
        source == GCDownloadSource.GETCOMICS_TORRENT
        and content_type == "application/x-bittorrent"
    ):
        # Link is to torrent file
        hash = sha1(bencode(get_torrent_info(await r.read()))).hexdigest()
        return (
            "magnet:?xt=urn:btih:" + hash + "&tr=udp://tracker.cyberia.is:6969/announce&tr=udp://tracker.port443.xyz:6969/announce&tr=http://tracker3.itzmx.com:6961/announce&tr=udp://tracker.moeking.me:6969/announce&tr=http://vps02.net.orel.ru:80/announce&tr=http://tracker.openzim.org:80/announce&tr=udp://tracker.skynetcloud.tk:6969/announce&tr=https://1.tracker.eu.org:443/announce&tr=https://3.tracker.eu.org:443/announce&tr=http://re-tracker.uz:80/announce&tr=https://tracker.parrotsec.org:443/announce&tr=udp://explodie.org:6969/announce&tr=udp://tracker.filemail.com:6969/announce&tr=udp://tracker.nyaa.uk:6969/announce&tr=udp://retracker.netbynet.ru:2710/announce&tr=http://tracker.gbitt.info:80/announce&tr=http://tracker2.dler.org:80/announce",
            TorrentDownload
        )

    else:
        # Link is direct download from getcomics
        # ('Main Server', 'Mirror Server', 'Link 1', 'Link 2', etc.)
        return url, DirectDownload


async def __purify_download_group(
    group: DownloadGroup,
    volume_id: int,
    issue_id: Union[int, None],
    web_link: str,
    web_title: Union[str, None],
    forced_match: bool = False
) -> Tuple[Union[Download, None], bool]:
    """Turn a download group into a working link and client for the link.

    Args:
        group (DownloadGroup): The download group to convert.

        volume_id (int): The ID of the volume that the download group is for.

        issue_id (Union[int, None]): The ID of the issue that the download group
        is for.

        web_link (str): The link to the web page.

        web_title (Union[str, None]): The title of the GC article.

        forced_match (bool, optional): Don't rename the downloaded files,
        even if the setting for it is enabled.
            Defaults to False.

    Returns:
        Tuple[Union[Download, None], bool]: If successful, the download and
        `False`. If unsuccessful, `None` and whether it failed because the
        limit of a service was reached.
    """
    limit_reached = False
    for source, links in group['links'].items():
        for link in iter_commit(links):
            try:
                pure_link, DownloadClass = await __purify_link(source, link)

            except LinkBroken as lb:
                # Link broken, source not supported
                add_to_blocklist(
                    web_link=web_link,
                    web_title=web_title,
                    web_sub_title=group['web_sub_title'],
                    download_link=link,
                    source=source, # type: ignore
                    volume_id=volume_id,
                    issue_id=issue_id,
                    reason=lb.reason
                )
                continue

            try:
                dl_instance: Download = DownloadClass(
                    download_link=pure_link,
                    volume_id=volume_id,
                    covered_issues=group["info"]["issue_number"],
                    source_type=source, # type: ignore
                    source_name=source.value,
                    web_link=web_link,
                    web_title=web_title,
                    web_sub_title=group['web_sub_title'],
                    forced_match=forced_match
                )

            except LinkBroken as lb:
                # DL limit reached, link broken
                add_to_blocklist(
                    web_link=web_link,
                    web_title=web_title,
                    web_sub_title=group['web_sub_title'],
                    download_link=pure_link,
                    source=source, # type: ignore
                    volume_id=volume_id,
                    issue_id=issue_id,
                    reason=lb.reason
                )

            except IssueNotFound:
                # The group refers to issues that don't exist in the
                # volume, and download is not forced.
                return None, False

            except DownloadLimitReached:
                # Link works but the download limit for the service is
                # reached
                limit_reached = True

            else:
                return dl_instance, limit_reached

    return None, limit_reached


async def _test_paths(
    link_paths: List[List[DownloadGroup]],
    web_link: str,
    web_title: Union[str, None],
    volume_id: int,
    issue_id: Union[int, None] = None,
    forced_match: bool = False
) -> List[Download]:
    """Test the links of the paths and determine, based on which links work,
    which path to go for.

    Args:
        link_paths (List[List[DownloadGroup]]): The link paths.

        web_link (str): The link to the GC article.

        web_title (Union[str, None]): The title of the GC article.

        volume_id (int): The ID of the volume that the download is for.

        issue_id (Union[int, None], optional): The ID of the issue that the
        download is for.
            Defaults to None.

        forced_match (bool, optional): Don't rename the downloaded files,
        even if the setting for it is enabled.
            Defaults to False.

    Raises:
        FailedGCPage: With `.reason = FailReason.NO_WORKING_LINKS`, it means
        not a single working link was found on the page.

        FailedGCPage: With `.reason = FailReason.LIMIT_REACHED`, it means
        not a single working link was found, but part of the links didn't work
        because the limit of the service was reached (which will go away).

    Returns:
        List[Download]: A list of downloads.
    """
    downloads: Tuple[Union[Download, None]] = tuple()
    limit_reached: Tuple[bool] = tuple()
    for path in link_paths:
        downloads, limit_reached = zip(*(await gather(*(
            __purify_download_group(
                group,
                volume_id,
                issue_id,
                web_link,
                web_title,
                forced_match
            )
            for group in path
        ))))

        if not downloads:
            continue

        LOGGER.debug(f'Chosen links: {downloads}')
        return [d for d in downloads if d is not None]

    # Nothing worked
    if any(limit_reached):
        raise FailedGCPage(FailReason.LIMIT_REACHED)
    else:
        raise FailedGCPage(FailReason.NO_WORKING_LINKS)


# region Searching
async def search_getcomics(
    session: AsyncSession,
    query: str
) -> List[SearchResultData]:
    """Give the search results from GC for the query.

    Args:
        session (AsyncSession): The session to make the requests with.
        query (str): The query to use.

    Returns:
        List[SearchResultData]: The search results.
    """
    # Fetch first page and determine max pages
    first_page = await session.get_text(
        Constants.GC_SITE_URL,
        params={"s": query}
    )
    first_soup = BeautifulSoup(first_page, "html.parser")
    max_page = min(
        _get_max_page(first_soup),
        10
    )

    # Fetch pages beyond first concurrently
    other_tasks = [
        session.get_text(
            f"{Constants.GC_SITE_URL}/page/{page}",
            params={"s": query}
        )
        for page in range(2, max_page + 1)
    ]

    if FlareSolverr().is_enabled():
        # FlareSolverr available, run at full speed
        other_htmls = await gather(*other_tasks)
    else:
        # FlareSolverr not available, run at sequencial speed
        other_htmls = [
            await task
            for task in other_tasks
        ]

    other_soups = [
        BeautifulSoup(html, "html.parser")
        for html in other_htmls
    ]

    # Process the search results on each page
    formatted_results: List[SearchResultData] = [
        {
            **extract_filename_data(
                article[1],
                assume_volume_number=False,
                fix_year=True
            ),
            "link": article[0],
            "display_title": article[1],
            "source": Constants.GC_SOURCE_TERM
        }
        for soup in (first_soup, *other_soups)
        for article in _get_articles(soup)
    ]

    return formatted_results


# region Processing
class GetComicsPage:
    def __init__(self, link: str) -> None:
        """Process a GC article.

        Args:
            link (str): The link to the article.
        """
        self.link = link
        self.title: Union[str, None] = None
        self.download_groups: List[DownloadGroup] = []
        return

    async def load_data(self) -> None:
        """Scrape and process the data of the page, in prepration of creating
        downloads from the page.

        Raises:
            FailedGCPage: Failed to fetch the GC page.
        """
        LOGGER.debug(f"Extracting download links from {self.link}")

        async with AsyncSession() as session:
            try:
                response = await session.get(self.link)
                if not response.ok:
                    raise ClientError

                soup = BeautifulSoup(await response.text(), 'html.parser')

            except ClientError:
                raise FailedGCPage(FailReason.BROKEN)

        self.title = _get_title(soup)
        self.download_groups = _get_download_groups(soup)
        return

    async def create_downloads(
        self,
        volume_id: int,
        issue_id: Union[int, None] = None,
        force_match: bool = False
    ) -> List[Download]:
        """Create downloads from the links on the page for a certain volume
        (and issue if given).

        Args:
            volume_id (int): The volume's ID for which to (possibly) filter and
            create the downloads.

            issue_id (Union[int, None], optional): The ID of the issue for which
            the download is intended.
                Defaults to None.

            force_match (bool, optional): Don't filter the download groups for
            the volume, but instead just download all content from the page.
                Defaults to False.

        Raises:
            FailedGCPage: Something went wrong with creating the downloads.
            See the `reason` attr of the exception.

        Returns:
            List[Download]: The list of downloads coming from the GC page, for
            the volume.
        """
        link_paths = _create_link_paths(
            self.download_groups,
            volume_id,
            force_match
        )

        if not link_paths:
            raise FailedGCPage(FailReason.NO_MATCHES)

        result = await _test_paths(
            link_paths,
            web_link=self.link,
            web_title=self.title,
            volume_id=volume_id,
            issue_id=issue_id,
            forced_match=force_match
        )

        return result
