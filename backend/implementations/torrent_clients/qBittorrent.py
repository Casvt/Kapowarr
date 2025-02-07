# -*- coding: utf-8 -*-

from re import IGNORECASE, compile
from time import time
from typing import Any, Dict, List, Union

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ExternalClientNotWorking
from backend.base.definitions import Constants, DownloadState, DownloadType
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_clients import BaseExternalClient
from backend.internals.settings import Settings

filename_magnet_link = compile(r'(?<=&dn=).*?(?=&)', IGNORECASE)


class qBittorrent(BaseExternalClient):
    client_type = 'qBittorrent'
    download_type = DownloadType.TORRENT

    required_tokens = ('title', 'base_url', 'username', 'password')

    state_mapping = {
        'queuedDL': DownloadState.QUEUED_STATE,
        'pausedDL': DownloadState.PAUSED_STATE,
        'checkingDL': DownloadState.DOWNLOADING_STATE,
        'metaDL': DownloadState.DOWNLOADING_STATE,
        'checkingResumeData': DownloadState.DOWNLOADING_STATE,
        'downloading': DownloadState.DOWNLOADING_STATE,
        'forcedDL': DownloadState.DOWNLOADING_STATE,

        'queuedUP': DownloadState.SEEDING_STATE,
        'uploading': DownloadState.SEEDING_STATE,
        'forcedUP': DownloadState.SEEDING_STATE,
        'checkingUP': DownloadState.SEEDING_STATE,
        'stalledUP': DownloadState.SEEDING_STATE,

        'pausedUP': DownloadState.IMPORTING_STATE,
        'error': DownloadState.FAILED_STATE
    }

    def __init__(self, client_id: int) -> None:
        super().__init__(client_id)

        self.ssn: Union[Session, None] = None
        self.torrent_hashes: Dict[str, Union[int, None]] = {}
        self.settings = Settings()
        return

    @staticmethod
    def _login(
        base_url: str,
        username: Union[str, None],
        password: Union[str, None]
    ) -> Union[Session, str]:

        ssn = Session()
        if username and password:
            params = {
                'username': username,
                'password': password
            }
        else:
            params = {}

        try:
            auth_request = ssn.post(
                f'{base_url}/api/v2/auth/login',
                data=params
            )

        except RequestException:
            LOGGER.exception("Can't connect to qBittorrent instance: ")
            return "Can't connect; invalid base URL"

        if auth_request.status_code == 404:
            LOGGER.error(
                f"Can't connect or version too low of qBittorrent instance: {auth_request.text}"
            )
            return "Invalid base URL or version too low; at least v4.1"

        if not auth_request.ok:
            LOGGER.error(
                f"Not connected to qBittorrent instance: {auth_request.text}"
            )
            return "Invalid instance; not Qbittorrent"

        auth_success = auth_request.headers.get('set-cookie') is not None

        if not auth_success:
            LOGGER.error(
                f"Failed to authenticate for qBittorrent instance: {auth_request.text}"
            )
            return "Can't authenticate"

        return ssn

    def add_download(
        self,
        download_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        if download_name is not None:
            download_link = filename_magnet_link.sub(
                download_name, download_link
            )

        files = {
            'urls': (None, download_link),
            'savepath': (None, target_folder),
            'category': (None, Constants.TORRENT_TAG)
        }

        if not self.ssn:
            result = self._login(self.base_url, self.username, self.password)
            if isinstance(result, str):
                raise ExternalClientNotWorking(result)
            self.ssn = result

        self.ssn.post(
            f'{self.base_url}/api/v2/torrents/add',
            files=files
        )
        t_hash = download_link.split('urn:btih:')[1].split('&')[0]
        self.torrent_hashes[t_hash] = None
        return t_hash

    def get_download(self, download_id: str) -> Union[dict, None]:
        if not self.ssn:
            result = self._login(self.base_url, self.username, self.password)
            if isinstance(result, str):
                raise ExternalClientNotWorking(result)
            self.ssn = result

        r: List[Dict[str, Any]] = self.ssn.get(
            f'{self.base_url}/api/v2/torrents/info',
            params={'hashes': download_id}
        ).json()
        if not r:
            if download_id in self.torrent_hashes:
                return None
            else:
                return {}

        result = r[0]

        state = self.state_mapping.get(
            result['state'],
            DownloadState.IMPORTING_STATE
        )
        if result['state'] in ('metaDL', 'stalledDL', 'checkingDL'):
            # Torrent is failing
            if self.torrent_hashes[download_id] is None:
                self.torrent_hashes[download_id] = round(time())
                state = DownloadState.DOWNLOADING_STATE

            else:
                timeout = self.settings.sv.failing_torrent_timeout
                if timeout and (
                    time() - (self.torrent_hashes[download_id] or 0)
                    > timeout
                ):
                    state = DownloadState.FAILED_STATE
        else:
            self.torrent_hashes[download_id] = None

        return {
            'size': result['total_size'],
            'progress': round(result['progress'] * 100, 2),
            'speed': result['dlspeed'],
            'state': state
        }

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        if not self.ssn:
            result = self._login(self.base_url, self.username, self.password)
            if isinstance(result, str):
                raise ExternalClientNotWorking(result)
            self.ssn = result

        self.ssn.post(
            f'{self.base_url}/api/v2/torrents/delete',
            data={
                'hashes': download_id,
                'deleteFiles': delete_files
            }
        )
        del self.torrent_hashes[download_id]
        return

    @staticmethod
    def test(
        base_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        api_token: Union[str, None] = None
    ) -> Union[str, None]:
        result = qBittorrent._login(
            base_url,
            username,
            password
        )

        if isinstance(result, str):
            return result
        return None
