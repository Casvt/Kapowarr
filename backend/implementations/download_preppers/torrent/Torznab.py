# -*- coding: utf-8 -*-

from typing import List, Union

from backend.base.custom_exceptions import EnqueuingDownloadFailure
from backend.base.definitions import (Download, DownloadClientIdentifier,
                                      DownloadPrepper, DownloadService,
                                      DownloadType,
                                      EnqueuingDownloadFailureReason,
                                      FilenameData)
from backend.base.helpers import Session
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_prepper_manager import DownloadPreppers
from backend.implementations.indexer_client_manager import IndexerClients


@DownloadPreppers.register_prepper(DownloadType.TORRENT, "Torznab")
class TorznabPrepper(DownloadPrepper):
    @property
    def web_title(self) -> None:
        return None

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

    def get_downloads(self) -> List[Download]:
        if not self.link.startswith("magnet:?"):
            # HTTP link that redirects to magnet link
            with Session() as session:
                response = session.get(
                    self.link,
                    stream=True,
                    allow_redirects=False
                )
            self.link = response.headers.get("Location", "")
            if not self.link.startswith("magnet:?"):
                raise EnqueuingDownloadFailure(
                    EnqueuingDownloadFailureReason.LINK_BROKEN
                )

        download = DownloadClients.get_client(DownloadClientIdentifier.TORRENT)(
            download_link=self.link,
            volume_id=self.volume_id,
            covered_issues=self.title_data["issue_number"],
            download_service=DownloadService.TORRENT,
            source_name=IndexerClients.get_client(self.indexer_id).title,
            web_link=None,
            web_title=None,
            web_sub_title=None,
            forced_match=self.force_match
        )
        return [download]
