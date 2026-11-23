# -*- coding: utf-8 -*-

from typing import List, Optional, Union

from requests import RequestException

from backend.base.custom_exceptions import (EnqueuingDownloadFailure,
                                            ExternalClientNotFound,
                                            IssueNotFound)
from backend.base.definitions import (Download, DownloadClientIdentifier,
                                      DownloadPrepper, DownloadService,
                                      DownloadType,
                                      EnqueuingDownloadFailureReason)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import Session
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_prepper_manager import DownloadPreppers
from backend.implementations.indexer_client_manager import IndexerClients


@DownloadPreppers.register_prepper(DownloadType.USENET, "Newznab")
class NewznabPrepper(DownloadPrepper):
    @property
    def web_title(self) -> Optional[str]:
        return self._web_title

    def __init__(
        self,
        link: str,
        indexer_id: int,
        title: str,
        volume_id: int,
        issue_id: Union[int, None] = None,
        force_match: bool = False
    ) -> None:
        self.link = link
        self.indexer_id = indexer_id
        self.title = title
        self.title_data = extract_filename_data(
            title,
            assume_volume_number=False,
            fix_year=True
        )
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

        return self.title

    def get_downloads(self) -> List[Download]:
        self._web_title = self.__fetch_nzb()

        try:
            download = DownloadClients.get_client(
                DownloadClientIdentifier.USENET
            )(
                download_link=self.link,
                volume_id=self.volume_id,
                covered_issues=self.title_data["issue_number"],
                download_service=DownloadService.USENET,
                source_name=IndexerClients.get_client(
                    self.indexer_id
                ).title,
                web_link=None,
                web_title=self._web_title,
                web_sub_title=None,
                forced_match=self.force_match
            )

        except IssueNotFound:
            raise EnqueuingDownloadFailure(
                EnqueuingDownloadFailureReason.NO_MATCHES
            )

        except ExternalClientNotFound:
            raise EnqueuingDownloadFailure(
                EnqueuingDownloadFailureReason.NO_DOWNLOAD_CLIENT_AVAILABLE
            )

        return [download]
