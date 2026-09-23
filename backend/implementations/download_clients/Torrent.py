# -*- coding: utf-8 -*-

from asyncio import run
from os.path import basename, join, splitext
from threading import Event
from typing import Any, Dict, Tuple, Union

from magnet2torrent import FailedToFetchException, Magnet2Torrent

from backend.base.custom_exceptions import DownloadLinkBroken, IssueNotFound
from backend.base.definitions import (DownloadClientIdentifier,
                                      DownloadService, DownloadState,
                                      DownloadType, ExternalDownload,
                                      ExternalDownloadClient, FileConstants)
from backend.base.helpers import get_torrent_info
from backend.base.logging import LOGGER
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload
from backend.implementations.external_client_manager import ExternalClients
from backend.implementations.naming import generate_issue_name
from backend.implementations.remote_mapping import RemoteMappings
from backend.implementations.volumes import Volume
from backend.internals.settings import Settings


@DownloadClients.register_client(DownloadClientIdentifier.TORRENT)
class TorrentDownload(ExternalDownload, BaseDirectDownload):
    @property
    def external_client(self) -> ExternalDownloadClient:
        return self._external_client

    @external_client.setter
    def external_client(self, value: ExternalDownloadClient) -> None:
        self._external_client = value
        return

    @property
    def external_id(self) -> Union[str, None]:
        return self._external_id

    @property
    def sleep_event(self) -> Event:
        return self._sleep_event

    def __init__(
        self,
        download_link: str,

        volume_id: int,
        covered_issues: Union[float, Tuple[float, float], None],

        download_service: DownloadService,
        source_name: str,

        web_link: Union[str, None],
        web_title: Union[str, None],
        web_sub_title: Union[str, None],

        forced_match: bool = False,
        external_client: Union[ExternalDownloadClient, None] = None
    ) -> None:
        LOGGER.debug(
            'Creating download: %s',
            download_link
        )

        settings = Settings().sv
        volume = Volume(volume_id)

        self._download_link = self._pure_link = download_link
        self._volume_id = volume_id
        self._issue_id = None
        self._covered_issues = covered_issues
        self._download_service = download_service
        self._source_name = source_name
        self._web_link = web_link
        self._web_title = web_title
        self._web_sub_title = web_sub_title

        self._id = None
        self._state = DownloadState.QUEUED_STATE
        self._progress = 0.0
        self._speed = 0.0
        self._size = -1
        self._download_thread = None
        self._download_folder = settings.download_folder
        self._sleep_event = Event()

        self._external_id: Union[str, None] = None
        if external_client:
            self._external_client = external_client
        else:
            self._external_client = ExternalClients.get_least_used_client(
                DownloadType.TORRENT
            )

        try:
            if isinstance(covered_issues, float):
                self._issue_id = volume.get_issue_from_number(covered_issues).id

        except IssueNotFound as e:
            if not forced_match:
                raise e

        # Find name of torrent as that becomes folder that media is
        # downloaded in
        torrent_name = run(self._fetch_torrent_name())
        if not torrent_name:
            raise DownloadLinkBroken(self.download_link)

        self._filename_body = ''
        if settings.rename_downloaded_files:
            try:
                self._filename_body = generate_issue_name(
                    volume.get_data(),
                    covered_issues
                )

            except IssueNotFound as e:
                if not forced_match:
                    raise e

        if not self._filename_body:
            if torrent_name.endswith(FileConstants.SCANNABLE_EXTENSIONS):
                self._filename_body = splitext(torrent_name)[0]
            else:
                self._filename_body = torrent_name

        self._title = basename(self._filename_body)
        self._files = [join(self._download_folder, torrent_name)]
        return

    async def _fetch_torrent_name(self) -> Union[str, None]:
        """Get the torrent name that will be used as the folder/file name from
        the magnet link.

        Returns:
            Union[str, None]: The torrent name, or None if it failed to get it.
        """
        m2t = Magnet2Torrent(self._download_link, use_additional_trackers=True)
        try:
            raw_data = (await m2t.retrieve_torrent())[1]
        except FailedToFetchException:
            return None

        return get_torrent_info(raw_data)[b"name"].decode()

    def run(self) -> None:
        self._external_id = self.external_client.add_download(
            self.download_link,
            RemoteMappings.local_to_remote(
                self._external_client.id,
                self._download_folder
            ),
            self.title
        )
        return

    def update_status(self) -> None:
        if not self.external_id:
            return

        torrent_status = self.external_client.get_download(self.external_id)
        if not torrent_status:
            if torrent_status is None:
                self._state = DownloadState.CANCELED_STATE
            return

        self._progress = torrent_status['progress']
        self._speed = torrent_status['speed']
        self._size = torrent_status['size']
        if self.state not in (
            DownloadState.CANCELED_STATE,
            DownloadState.SHUTDOWN_STATE
        ):
            self._state = torrent_status['state']

        return

    def remove_from_client(self, delete_files: bool) -> None:
        if not self.external_id:
            return

        self.external_client.delete_download(self.external_id, delete_files)
        return

    def stop(self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        self._state = state
        self._sleep_event.set()
        return

    def as_dict(self) -> Dict[str, Any]:
        return {
            **super().as_dict(),
            'client': self.external_client.id if self._external_client else None
        }
