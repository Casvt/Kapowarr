# -*- coding: utf-8 -*-

"""
Getting downloads from a GC page
"""

from hashlib import sha1
from re import IGNORECASE, compile
from typing import Callable, Dict, List, Tuple, Union

from bencoding import bencode
from bs4 import BeautifulSoup, Tag
from requests.exceptions import RequestException

from backend.blocklist import add_to_blocklist, blocklist_contains
from backend.custom_exceptions import (DownloadLimitReached,
                                       FailedGCPage, LinkBroken)
from backend.db import get_db
from backend.download_direct_clients import (DirectDownload, Download,
                                             MediaFireDownload,
                                             MediaFireFolderDownload,
                                             MegaDownload, PixelDrainDownload,
                                             WeTransferDownload)
from backend.download_torrent_clients import TorrentDownload
from backend.enums import (BlocklistReason, DownloadSource, FailReason,
                           GCDownloadSource, SpecialVersion)
from backend.file_extraction import extract_filename_data
from backend.helpers import (DownloadGroup, FilenameData,
                             Session, check_overlapping_issues,
                             create_range, get_torrent_info)
from backend.logging import LOGGER
from backend.matching import GC_group_filter
from backend.naming import (generate_empty_name, generate_issue_name,
                            generate_issue_range_name, generate_sv_name)
from backend.settings import Settings, download_source_versions
from backend.volumes import Volume

# autopep8: off
check_year = compile(r'\b\d{4}\b')
remove_year_suffix = compile(r'--\d{4}--$')
mega_regex = compile(r'https?://mega\.(nz|io)/(#(F\!|\!)|folder/|file/)', IGNORECASE)
mediafire_regex = compile(r'https?://www\.mediafire\.com/', IGNORECASE)
mediafire_dd_regex = compile(r'https?://download\d+\.mediafire\.com/', IGNORECASE)
wetransfer_regex = compile(r'(?:https?://we.tl/|wetransfer.com/downloads/)', IGNORECASE)
pixeldrain_regex = compile(r'https?://pixeldrain\.com/u/\w+', IGNORECASE)
extract_mediafire_regex = compile(r'window.location.href\s?=\s?\'https://download\d+\.mediafire.com/.*?(?=\')', IGNORECASE)
# autopep8: on


def _check_download_link(
    link_text: str,
    link: str,
    torrent_client_available: bool
) -> Union[GCDownloadSource, None]:
    """Check if download link is supported and allowed.

    Args:
        link_text (str): The title of the link.
        link (str): The link itself.
        torrent_client_available (bool): Whether or not a torrent client is available.

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


link_filter_1: Callable[[Tag], bool] = lambda e: (
    e.name == 'p'
    and 'Language' in e.text
    and e.find('p') is None
)


def _extract_button_links(
    body: Tag,
    torrent_client_available: bool
) -> Dict[str, Dict[GCDownloadSource, List[str]]]:
    """Extract download groups that are a list of big buttons.

    Args:
        body (Tag): The body to extract from.
        torrent_client_available (bool): Whether or not a client is available.

    Returns:
        Dict[str, Dict[GCDownloadSource, List[str]]]: The download groups.
        Follows format described in `_extract_get_comics_links()`.
    """
    download_groups: Dict[str, Dict[GCDownloadSource, List[str]]] = {}
    for result in body.find_all(link_filter_1):
        result: Tag
        extracted_title = result.get_text('\x00')
        title = extracted_title.partition('\x00')[0]

        if 'variant cover' in title.lower():
            continue

        if (
            "Year :\x00\xa0" in extracted_title
            and not check_year.search(title)
        ):
            # Append year to title
            year = (
                extracted_title
                .split("Year :\x00\xa0")[1]
                .split(" |")[0]
            )
            title += ' --' + year + '--'

        if not result.next_sibling:
            continue
        for e in result.next_sibling.next_elements: # type: ignore
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
                match = _check_download_link(
                    link_title,
                    href,
                    torrent_client_available
                )
                if match:
                    (download_groups
                        .setdefault(title, {})
                        .setdefault(match, [])
                        .append(href)
                    )

    return download_groups


link_filter_2: Callable[[Tag], bool] = lambda e: (
    e.name == 'li'
    and e.parent is not None
    and e.parent.name == 'ul'
    and e.find('a') is not None
)


def _extract_list_links(
    body: Tag,
    torrent_client_available: bool
) -> Dict[str, Dict[GCDownloadSource, List[str]]]:
    """Extract download groups that are in a unsorted list.

    Args:
        body (Tag): The body to extract from.
        torrent_client_available (bool): Whether or not a client is available.

    Returns:
        Dict[str, Dict[GCDownloadSource, List[str]]]: The download groups.
        Follows format described in `_extract_get_comics_links()`.
    """
    download_groups: Dict[str, Dict[GCDownloadSource, List[str]]] = {}
    for result in body.find_all(link_filter_2):
        title: str = result.get_text('\x00').partition('\x00')[0]

        if 'variant cover' in title.lower():
            continue

        for group_link in result.find_all('a'):
            group_link: Tag
            if group_link.get('href') is None:
                continue
            link_title = group_link.text.strip().lower()
            href = create_range(group_link.get('href') or '')[0]
            if not href:
                continue
            match = _check_download_link(
                link_title,
                href,
                torrent_client_available
            )
            if match:
                (download_groups
                    .setdefault(title, {})
                    .setdefault(match, [])
                    .append(href)
                )

    return download_groups


def _sort_link_paths(p: List[DownloadGroup]) -> Tuple[float, int]:
    """Sort the link paths. TPB's are sorted highest, then from largest range to least.

    Args:
        p (List[DownloadGroup]): A link path

    Returns:
        Tuple[float, int]: The rating (lower is better)
    """
    if p[0]['info']['special_version']:
        return (0.0, 0)

    issues_covered = 0
    for entry in p:
        if isinstance(entry['info']['issue_number'], float):
            issues_covered += 1
        elif isinstance(entry['info']['issue_number'], tuple):
            issues_covered += (
                entry['info']['issue_number'][1]
                -
                entry['info']['issue_number'][0]
            )

    return (1 / issues_covered, len(p))


def _create_link_paths(
    download_groups: Dict[str, Dict[GCDownloadSource, List[str]]],
    volume_id: int
) -> List[List[DownloadGroup]]:
    """Based on the download groups, find different "paths" to download
    the most amount of content. On the same page, there might be a download
    for `TPB + Extra's`, `TPB`, `Issue A-B` and for `Issue C-D`. This function
    creates "paths" that contain links that together download as much content
    without overlapping. So a path would be created for `TPB + Extra's`. A
    second path would be created for `TPB` and a third path for
    `Issue A-B` + `Issue C-D`. Paths 2 and on are basically backup options for
    if path 1 doesn't work, to still get the most content out of the page.

    Args:
        download_groups (Dict[str, Dict[GCDownloadSource, List[str]]]):
        The download groups. Output of `download._extract_get_comics_links()`.
        volume_id (int): The id of the volume.

    Returns:
        List[List[DownloadGroup]]: The list contains all paths. Each path is
        a list of download groups. The `web_sub_title` has the group name.
        The `info` key has as it's value the output of
        `file_extraction.extract_filename_data()` for the title of the group.
        The `links` key contains the download links grouped together with
        their service.
    """
    LOGGER.debug('Creating link paths')

    # Get info of volume
    volume = Volume(volume_id)
    volume_data = volume.get_keys(
        ('title', 'year', 'special_version')
    )
    last_issue_date = volume['last_issue_date']
    service_preference: List[str] = Settings()['service_preference']

    link_paths: List[List[DownloadGroup]] = []
    for desc, sources in download_groups.items():
        processed_desc = extract_filename_data(
            desc,
            assume_volume_number=False,
            fix_year=True
        )
        if GC_group_filter(
            processed_desc,
            volume_id,
            volume_data.title,
            volume_data.year,
            last_issue_date,
            volume_data.special_version
        ):
            # Group matches/contains what is desired to be downloaded
            sources = {
                s: sources[s]
                for s in sorted(
                    sources,
                    key=lambda k: service_preference.index(k.value)
                )
            }
            path_entry: DownloadGroup = {
                'web_sub_title': remove_year_suffix.sub('', desc).strip(),
                'info': processed_desc,
                'links': sources
            }
            if (volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
            and (
                processed_desc['special_version'] == SpecialVersion.TPB
                or isinstance(processed_desc['volume_number'], tuple)
            )):
                processed_desc['special_version'] = SpecialVersion.VOLUME_AS_ISSUE.value

            if (
                processed_desc['special_version'] is not None
                and processed_desc['special_version'] != SpecialVersion.VOLUME_AS_ISSUE
            ):
                if volume_data.special_version in (
                    SpecialVersion.HARD_COVER,
                    SpecialVersion.ONE_SHOT
                ):
                    processed_desc['special_version'] = volume_data.special_version.value

                link_paths.append([path_entry])

            else:
                # Find path with ranges and single issues that doesn't have
                # a link that already covers this one
                for path in link_paths:
                    for entry in path:
                        if entry['info']['special_version'] == SpecialVersion.VOLUME_AS_ISSUE:
                            if entry['info']['volume_number'] == processed_desc['volume_number']:
                                break

                        elif entry['info']['special_version'] is not None:
                            break

                        elif check_overlapping_issues(
                            entry['info']['issue_number'], # type: ignore
                            processed_desc['issue_number'] # type: ignore
                        ):
                            break

                    else:
                        # No conflicts found so add to path
                        path.append(path_entry)
                        break
                else:
                    # Conflict in all paths found so start a new one
                    link_paths.append([path_entry])

    link_paths.sort(key=_sort_link_paths)

    LOGGER.debug(f'Link paths: {link_paths}')
    return link_paths


def _generate_name(
    volume_id: int,
    download_info: FilenameData,
    name_volume_as_issue: bool
) -> str:
    """Generate filename based on info.

    Args:
        volume_id (int): The ID of the volume for which the file is.
        download_info (FilenameData): Filename data for download group title.
        name_volume_as_issue (bool): Whether or not to name the volume as an
        issue.

    Returns:
        str: The generated name.
    """
    if download_info['special_version'] in (
        SpecialVersion.TPB,
        SpecialVersion.ONE_SHOT,
        SpecialVersion.HARD_COVER
    ):
        return generate_sv_name(volume_id)

    if download_info['special_version'] == SpecialVersion.VOLUME_AS_ISSUE:
        if name_volume_as_issue:
            if isinstance(download_info['volume_number'], tuple):
                return generate_issue_range_name(
                    volume_id,
                    *download_info['volume_number']
                )
            else:
                return generate_issue_name(
                    volume_id,
                    download_info['volume_number'] # type: ignore
                )
        else:
            return generate_empty_name(
                volume_id,
                download_info['volume_number']
            )

    if isinstance(download_info['issue_number'], tuple):
        return generate_issue_range_name(
            volume_id,
            *download_info['issue_number']
        )

    return generate_issue_name(
        volume_id,
        download_info['issue_number'] # type: ignore
    )


def purify_link(link: str) -> dict:
    """Extract the link that directly leads to the download from the link
    on the getcomics page

    Args:
        link (str): The link on the getcomics page

    Raises:
        LinkBroken: Link is invalid, not supported or broken

    Returns:
        dict: The pure link,
        a download class for the correct service (child of `download_general.Download`)
        and the source title.
    """
    LOGGER.debug(f'Purifying link: {link}')
    if link.startswith('magnet:?'):
        # Link is already magnet link
        return {
            'download_link': link,
            'target': TorrentDownload,
            'source': DownloadSource.GETCOMICS_TORRENT
        }

    elif link.startswith('http'):
        r = Session().get(link, stream=True)
        url = r.url

        if mega_regex.search(url):
            # Link is mega
            if '#F!' in url:
                # Link is not supported (folder)
                raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)

            if '/folder/' in url:
                # Link is not supported (folder)
                raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)

            return {
                'download_link': url,
                'target': MegaDownload,
                'source': DownloadSource.MEGA
            }

        elif mediafire_regex.search(url):
            # Link is mediafire
            if 'error.php' in url:
                # Link is broken
                raise LinkBroken(BlocklistReason.LINK_BROKEN)

            elif '/folder/' in url:
                # Folder download
                return {
                    'download_link': url,
                    'target': MediaFireFolderDownload,
                    'source': DownloadSource.MEDIAFIRE
                }

            else:
                # File download
                return {
                    'download_link': url,
                    'target': MediaFireDownload,
                    'source': DownloadSource.MEDIAFIRE
                }

        elif mediafire_dd_regex.search(url):
            # Link is mediafire, but not to the page but instead the direct link
            if not r.ok:
                raise LinkBroken(BlocklistReason.LINK_BROKEN)

            return {
                'download_link': url,
                'target': DirectDownload,
                'source': DownloadSource.MEDIAFIRE
            }

        elif wetransfer_regex.search(url):
            # Link is wetransfer
            return {
                'download_link': url,
                'target': WeTransferDownload,
                'source': DownloadSource.WETRANSFER
            }

        elif pixeldrain_regex.search(url):
            # Link is pixeldrain
            return {
                'download_link': url,
                'target': PixelDrainDownload,
                'source': DownloadSource.PIXELDRAIN
            }

        elif r.headers.get('Content-Type', '') == 'application/x-bittorrent':
            # Link is torrent file
            hash = sha1(bencode(get_torrent_info(r.content))).hexdigest()
            return {
                'download_link': "magnet:?xt=urn:btih:" + hash + "&tr=udp://tracker.cyberia.is:6969/announce&tr=udp://tracker.port443.xyz:6969/announce&tr=http://tracker3.itzmx.com:6961/announce&tr=udp://tracker.moeking.me:6969/announce&tr=http://vps02.net.orel.ru:80/announce&tr=http://tracker.openzim.org:80/announce&tr=udp://tracker.skynetcloud.tk:6969/announce&tr=https://1.tracker.eu.org:443/announce&tr=https://3.tracker.eu.org:443/announce&tr=http://re-tracker.uz:80/announce&tr=https://tracker.parrotsec.org:443/announce&tr=udp://explodie.org:6969/announce&tr=udp://tracker.filemail.com:6969/announce&tr=udp://tracker.nyaa.uk:6969/announce&tr=udp://retracker.netbynet.ru:2710/announce&tr=http://tracker.gbitt.info:80/announce&tr=http://tracker2.dler.org:80/announce",
                'target': TorrentDownload,
                'source': DownloadSource.GETCOMICS_TORRENT
            }

        # Link is direct download from getcomics
        # ('Main Server', 'Mirror Server', 'Link 1', 'Link 2', etc.)
        return {
            'download_link': url,
            'target': DirectDownload,
            'source': DownloadSource.GETCOMICS
        }

    else:
        raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)


def _test_paths(
    link_paths: List[List[DownloadGroup]],
    web_link: str,
    web_title: Union[str, None],
    volume_id: int,
    issue_id: Union[int, None] = None
) -> Tuple[List[Download], Union[FailReason, None]]:
    """Test the links of the paths and determine, based on which links work, which path to go for.

    Args:
        link_paths (List[List[DownloadGroup]]): The link paths.
            Output of `download._process_extracted_get_comics_links()`.

        web_link (str): The link to the GC page.

        web_title (Union[str, None]): The title of the GC release.

        volume_id (int): The id of the volume.

        issue_id (Union[int, None], optional): The id of the issue for which
        the download is intended.
            Defaults to None.

    Returns:
        Tuple[List[Download], Union[FailReason, None]]:
            A list of downloads and the reason the list if empty is so.
    """
    cursor = get_db()
    limit_reached = None
    downloads: List[Download] = []
    settings = Settings()
    rename_downloaded_files = settings['rename_downloaded_files']
    name_volume_as_issue = settings['volume_as_empty']
    for path in link_paths:
        for download in path:
            if rename_downloaded_files:
                name = _generate_name(
                    volume_id,
                    download['info'],
                    name_volume_as_issue
                )

            else:
                name = ''

            # Find working link
            for links in download['links'].values():
                for link in links:
                    try:
                        # Maybe make purify link async so that all links can be
                        # purified 'at the same time'?
                        pure_link = purify_link(link)

                    except LinkBroken as lb:
                        # Link broken, source not supported
                        add_to_blocklist(
                            web_link=web_link,
                            web_title=web_title,
                            web_sub_title=download['web_sub_title'],
                            download_link=link,
                            source=None,
                            volume_id=volume_id,
                            issue_id=issue_id,
                            reason=lb.reason
                        )
                        cursor.connection.commit()
                        continue

                    try:
                        dl_instance: Download = pure_link['target'](
                            download_link=pure_link['download_link'],
                            filename_body=name,
                            source=pure_link['source'],
                            custom_name=rename_downloaded_files
                        )
                        dl_instance.web_sub_title = download['web_sub_title']

                    except LinkBroken as lb:
                        # DL limit reached, link broken
                        add_to_blocklist(
                            web_link=web_link,
                            web_title=web_title,
                            web_sub_title=download['web_sub_title'],
                            download_link=pure_link['download_link'],
                            source=pure_link['source'],
                            volume_id=volume_id,
                            issue_id=issue_id,
                            reason=lb.reason
                        )
                        cursor.connection.commit()

                    except DownloadLimitReached:
                        # Link works but the download limit for the service is
                        # reached
                        limit_reached = FailReason.LIMIT_REACHED

                    else:
                        downloads.append(dl_instance)
                        break
                else:
                    continue
                break
            else:
                # No working link found in group
                if download['info']['special_version']:
                    # Download is essential for group and it doesn't work so try
                    # next path
                    break
        else:
            if downloads:
                break
            else:
                # Try next path
                continue
        downloads = []

    LOGGER.debug(f'Chosen links: {downloads}')
    return downloads, limit_reached


class GetComicsPage:
    def __init__(self, link: str) -> None:
        """Make an instance that represents the GC page.

        Args:
            link (str): The link to the GC release page.

        Raises:
            FailedGCPage: The page is invalid. See the exceptions `reason` attr.
        """
        LOGGER.debug(f"Extracting download links from {link}")
        self.link = link

        try:
            self.__make_soup()
        except RequestException:
            raise FailedGCPage(FailReason.BROKEN)

        self.__extract_web_title()
        self.__extract_download_groups()
        return

    def __make_soup(self) -> None:
        """Fetch link and convert to a soup.

        Raises:
            RequestException: Failed to fetch link.
        """
        r = Session().get(self.link, stream=True)
        if not r.ok:
            raise RequestException

        self.soup = BeautifulSoup(r.text, "html.parser")
        return

    def __extract_web_title(self) -> None:
        """Extract the release title from the GC soup.
        """
        title_el = self.soup.find("h1")
        self.web_title = None if not title_el else title_el.text
        return

    def __extract_download_groups(self) -> None:
        """Go through the getcomics page and extract all download links.
        The links are grouped. All links in a group lead to the same download,
        only via different services (mega, direct download, mirror download, etc.).

        Args:
            soup (BeautifulSoup): The soup of the getcomics page.

        Returns:
            Dict[str, Dict[GCDownloadSource, List[str]]]: The outer dict maps the
            group name to the group. The group is a dict that maps each service in\
            the group to a list of links for that service.
            Example:
                {
                    'Amazing Spider-Man V1 Issue 1-10': {
                        GCDownloadSource.MEGA: ['https://mega.io/abc'],
                        GCDownloadSource.GetComics: [
                            'https://main.server.com/abc',
                            'https://mirror.server.com/abc'
                        ]
                    },
                    'Amazing Spider-Man V1 Issue 11-20': {...}
                }
        """
        LOGGER.debug('Extracting download groups')

        torrent_client_available = get_db().execute(
            "SELECT 1 FROM torrent_clients"
        ).fetchone() is not None

        body: Union[Tag, None] = self.soup.find(
            'section', {'class': 'post-contents'}) # type: ignore
        if not body:
            self.download_groups = {}
            return

        download_groups = {
            **_extract_button_links(body, torrent_client_available),
            **_extract_list_links(body, torrent_client_available)
        }

        LOGGER.debug(f'Download groups: {download_groups}')
        self.download_groups = download_groups
        return

    def create_downloads(self,
        volume_id: int,
        issue_id: Union[int, None] = None
    ) -> List[Download]:
        """Create downloads from the links on the page for a certain volume.

        Args:
            volume_id (int): The volume's ID for which to filter and create
            the downloads.

            issue_id (Union[int, None], optional): The id of the issue for which
            the download is intended.
                Defaults to None.

        Raises:
            FailedGCPage: Something went wrong with creating the downloads.
            See the `reason` attr of the exception.

        Returns:
            List[Download]: The list of downloads coming from the GC page, for
            the volume.
        """
        link_paths = _create_link_paths(
            self.download_groups,
            volume_id
        )

        if not link_paths:
            raise FailedGCPage(FailReason.NO_MATCHES)

        result, limit_reached = _test_paths(
            link_paths,
            web_link=self.link,
            web_title=self.web_title,
            volume_id=volume_id,
            issue_id=issue_id
        )

        if not result:
            if limit_reached:
                raise FailedGCPage(FailReason.LIMIT_REACHED)
            else:
                raise FailedGCPage(FailReason.NO_WORKING_LINKS)

        elif limit_reached:
            LOGGER.warning('Limit of download service reached')

        for d in result:
            d.web_link = self.link
            d.web_title = self.web_title

        return result
