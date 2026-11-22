# -*- coding: utf-8 -*-

from html import unescape
from re import IGNORECASE, compile
from typing import List, Optional, Union
from urllib.parse import unquote

from requests import RequestException

from backend.base.custom_exceptions import (EnqueuingDownloadFailure,
                                            ExternalClientNotFound,
                                            IssueNotFound)
from backend.base.definitions import (Download, DownloadClientIdentifier,
                                      DownloadPrepper, DownloadService,
                                      DownloadType,
                                      EnqueuingDownloadFailureReason,
                                      FilenameData)
from backend.base.helpers import Session
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_prepper_manager import DownloadPreppers
from backend.implementations.indexer_client_manager import IndexerClients
from backend.implementations.indexer_clients.usenet.Newznab import \
    RECENT_TITLES

CONTENT_DISPOSITION_NAME = compile(
    r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
    IGNORECASE
)
NZB_META_NAME = compile(
    r'<meta\s+type="name"\s*>([^<]+)</meta>',
    IGNORECASE
)
SUBJECT_FILENAME = compile(r'"([^"]+)"')
"The quoted filename in a usenet subject"
ARCHIVE_EXTENSIONS = compile(
    r'(\.part\d+)?(\.vol\d+\+\d+)?'
    r'\.(par2|rar|r\d\d|zip|7z|nzb|cbr|cbz|cb7|pdf|epub|sfv|nfo)$',
    IGNORECASE
)


def _clean_name(name: str) -> str:
    """Turn a usenet subject or filename into a release name.

    `(Asterix) - "Asterix - 36 - De Papyrus.par2" [01/16] yEnc` becomes
    `Asterix - 36 - De Papyrus`.
    """
    name = unescape(name).strip()
    quoted = SUBJECT_FILENAME.search(name)
    if quoted and ('yenc' in name.lower() or '[' in name):
        name = quoted.group(1)
    return ARCHIVE_EXTENSIONS.sub('', name).strip()


def _release_name(
    link: str,
    response_headers,
    nzb: str
) -> Union[str, None]:
    """Get the release name of an NZB.

    Args:
        link (str): The link the NZB was downloaded from.
        response_headers: The headers of the response that served the NZB.
        nzb (str): The NZB file.

    Returns:
        Union[str, None]: The release name, if found.
    """
    # The title the indexer gave in the search results
    if link in RECENT_TITLES:
        return RECENT_TITLES[link]

    disposition = response_headers.get('Content-Disposition') or ''
    match = CONTENT_DISPOSITION_NAME.search(disposition)
    if match:
        name = _clean_name(unquote(match.group(1)))
        if name:
            return name

    match = NZB_META_NAME.search(nzb)
    if match:
        name = _clean_name(match.group(1))
        if name:
            return name

    return None


@DownloadPreppers.register_prepper(DownloadType.USENET, "Newznab")
class NewznabPrepper(DownloadPrepper):
    @property
    def web_title(self) -> Optional[str]:
        return self._web_title

    def __init__(
        self,
        link: str,
        indexer_id: int,
        title_data: FilenameData,
        volume_id: int,
        issue_id: Union[int, None] = None,
        force_match: bool = False
    ) -> None:
        self.link = link
        self.indexer_id = indexer_id
        self.title_data = title_data
        self.volume_id = volume_id
        self.issue_id = issue_id
        self.force_match = force_match

        self._web_title = None
        return

    def __fetch_nzb(self) -> str:
        """Download the NZB, which checks that the link works and gives the
        release name.

        Raises:
            EnqueuingDownloadFailure: The link doesn't serve an NZB.

        Returns:
            str: The release name.
        """
        with Session() as session:
            try:
                response = session.get(self.link)
                if response.status_code == 429:
                    raise EnqueuingDownloadFailure(
                        EnqueuingDownloadFailureReason.LINK_RATE_LIMITED
                    )
                if not response.ok:
                    raise RequestException

            except RequestException:
                raise EnqueuingDownloadFailure(
                    EnqueuingDownloadFailureReason.WEBPAGE_BROKEN
                )

        nzb = response.text
        if '<nzb' not in nzb[:2000].lower():
            raise EnqueuingDownloadFailure(
                EnqueuingDownloadFailureReason.WEBPAGE_BROKEN
            )

        name = _release_name(self.link, response.headers, nzb)
        if not name:
            raise EnqueuingDownloadFailure(
                EnqueuingDownloadFailureReason.NO_MATCHES
            )
        return name

    def get_downloads(self) -> List[Download]:
        self._web_title = self.__fetch_nzb()

        try:
            download = DownloadClients.get_client(
                DownloadClientIdentifier.USENET)(
                download_link=self.link,
                volume_id=self.volume_id,
                covered_issues=self.title_data["issue_number"],
                download_service=DownloadService.USENET,
                source_name=IndexerClients.get_client(
                    self.indexer_id).title,
                web_link=None,
                web_title=self._web_title,
                web_sub_title=None,
                forced_match=self.force_match)

        except IssueNotFound:
            raise EnqueuingDownloadFailure(
                EnqueuingDownloadFailureReason.NO_MATCHES
            )

        except ExternalClientNotFound:
            raise EnqueuingDownloadFailure(
                EnqueuingDownloadFailureReason.NO_DOWNLOAD_CLIENT_AVAILABLE
            )

        return [download]
