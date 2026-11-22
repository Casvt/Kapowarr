# -*- coding: utf-8 -*-

"""
A download of an NZB by an external usenet client (e.g. SABnzbd).
"""

from os.path import basename, dirname, isfile, join
from threading import Event
from typing import Any, Dict, Tuple, Union

from backend.base.custom_exceptions import IssueNotFound
from backend.base.definitions import (DownloadClientIdentifier,
                                      DownloadService, DownloadState,
                                      DownloadType, ExternalDownload,
                                      ExternalDownloadClient)
from backend.base.logging import LOGGER
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload
from backend.implementations.external_client_manager import ExternalClients
from backend.implementations.naming import generate_issue_name
from backend.implementations.remote_mapping import RemoteMappings
from backend.implementations.volumes import Volume
from backend.internals.settings import Settings


@DownloadClients.register_client(DownloadClientIdentifier.USENET)
class UsenetDownload(ExternalDownload, BaseDirectDownload):
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
        LOGGER.debug('Creating usenet download: %s', web_title)

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
                DownloadType.USENET
            )

        try:
            if isinstance(covered_issues, float):
                self._issue_id = volume.get_issue_from_number(covered_issues).id

        except IssueNotFound as e:
            if not forced_match:
                raise e

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
            self._filename_body = web_title or 'usenet download'

        # The name the job gets in the usenet client, which becomes the name
        # of the folder it unpacks into
        self._title = basename(self._filename_body)
        # Best guess until the client reports where it put the files
        self._files = [join(self._download_folder, self._title)]
        return

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

        status = self.external_client.get_download(self.external_id)
        if not status:
            if status is None:
                self._state = DownloadState.CANCELED_STATE
            return

        self._progress = status['progress']
        self._speed = status['speed']
        self._size = status['size']

        if status.get('storage'):
            # Where the client put the files, translated to our filesystem.
            # For a job with one file, SABnzbd reports that file instead of
            # the job folder; the import expects the folder.
            storage = RemoteMappings.remote_to_local(
                self._external_client.id,
                status['storage']
            )
            if isfile(storage):
                storage = dirname(storage)
            self._files = [storage]

        if self.state not in (
            DownloadState.CANCELED_STATE,
            DownloadState.SHUTDOWN_STATE
        ):
            self._state = status['state']

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
