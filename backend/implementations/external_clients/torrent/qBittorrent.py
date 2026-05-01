# -*- coding: utf-8 -*-

from time import time
from typing import Any, Dict, Union

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason, Constants,
                                      DownloadState, DownloadType,
                                      ExternalClientField as ECF)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_client_manager import (
    BaseExternalClient, ExternalClients, filename_magnet_link)
from backend.internals.settings import Settings


@ExternalClients.register_client(
    DownloadType.TORRENT, 'qBittorrent',
    (ECF.TITLE, ECF.ENABLED, ECF.BASE_URL, ECF.USERNAME, ECF.PASSWORD)
)
class qBittorrent(BaseExternalClient):
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

        self.ssn = self._login(
            self.base_url, self.username, self.password
        )
        self.login_timeout: int = self.ssn.get(
            f'{self.base_url}/api/v2/app/preferences'
        ).json()["web_ui_session_timeout"]
        self.last_api_call = round(time())
        self.last_update: float = 0.0

        self.statuses: Dict[str, Union[Dict[str, Any], None]] = {}
        self.fail_timestamps: Dict[str, Union[int, None]] = {}
        self.settings = Settings()
        return

    @staticmethod
    def _login(
        base_url: str,
        username: Union[str, None],
        password: Union[str, None]
    ) -> Session:
        """Login into qBittorrent client.

        Args:
            base_url (str): Base URL of instance.
            username (Union[str, None]): Username to access client, if set.
            password (Union[str, None]): Password to access client, if set.

        Raises:
            ClientNotWorking: Can't connect to client.
            CredentialInvalid: Credentials are invalid.

        Returns:
            Session: Request session that is logged in.
        """
        ssn = Session()

        if username or password:
            params = {
                'username': username or '',
                'password': password or ''
            }

            try:
                auth_request = ssn.post(
                    f'{base_url}/api/v2/auth/login',
                    data=params
                )

            except RequestException:
                LOGGER.exception("Can't connect to qBittorrent instance: ")
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

            if auth_request.status_code == 404:
                LOGGER.error(
                    f"Can't connect or version too low of qBittorrent instance: {auth_request.text}"
                )
                # Should be at least v4.1
                raise ClientNotWorking(BrokenClientReason.VERSION_NOT_SUPPORTED)

            if not auth_request.ok:
                LOGGER.error(
                    f"Not connected to qBittorrent instance: {auth_request.text}"
                )
                raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

            auth_success = auth_request.headers.get('set-cookie') is not None

            if not auth_success:
                LOGGER.error(
                    f"Failed to authenticate for qBittorrent instance: {auth_request.text}"
                )
                raise CredentialInvalid

            return ssn

        try:
            version_request = ssn.get(f'{base_url}/api/v2/app/version')

        except RequestException:
            LOGGER.exception("Can't connect to qBittorrent instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if version_request.status_code == 404:
            LOGGER.error(
                f"Can't connect or version too low of qBittorrent instance: {version_request.text}"
            )
            raise ClientNotWorking(BrokenClientReason.VERSION_NOT_SUPPORTED)

        if version_request.status_code in (401, 403):
            LOGGER.error(
                f"Authentication required for qBittorrent instance: {version_request.text}"
            )
            raise CredentialInvalid

        if not version_request.ok:
            LOGGER.error(
                f"Not connected to qBittorrent instance: {version_request.text}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        return ssn

    def _ensure_login(self) -> None:
        if self.last_api_call + self.login_timeout < time():
            self.ssn = self._login(
                self._base_url, self._username, self._password
            )
            self.last_api_call = round(time())
        return

    def _update_statuses(self) -> None:
        self._ensure_login()

        try:
            torrents: Dict[str, Dict[str, Any]] = {
                torrent["hash"]: torrent
                for torrent in self.ssn.get(
                    f'{self.base_url}/api/v2/torrents/info',
                    params={'hashes': '|'.join(self.statuses)}
                ).json()
            }
            self.last_api_call = round(time())

        except RequestException:
            LOGGER.exception("Can't connect to qBittorrent instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        for t_hash in self.statuses:
            if t_hash not in torrents:
                self.statuses[t_hash] = None
                continue

            torrent = torrents[t_hash]

            state = self.state_mapping.get(
                torrent['state'],
                DownloadState.IMPORTING_STATE
            )
            if torrent['state'] in ('metaDL', 'stalledDL', 'checkingDL'):
                # Torrent is failing
                if self.fail_timestamps[t_hash] is None:
                    self.fail_timestamps[t_hash] = round(time())
                    state = DownloadState.DOWNLOADING_STATE

                else:
                    timeout = self.settings.sv.failing_download_timeout
                    if timeout and (
                        time() - (self.fail_timestamps[t_hash] or 0)
                        > timeout
                    ):
                        state = DownloadState.FAILED_STATE
            else:
                self.fail_timestamps[t_hash] = None

            self.statuses[t_hash] = {
                'size': torrent['total_size'],
                'progress': round(torrent['progress'] * 100, 2),
                'speed': torrent['dlspeed'],
                'state': state
            }

        self.last_update = time()
        return

    def add_download(
        self,
        download_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        self._ensure_login()

        if download_name is not None:
            download_link = filename_magnet_link.sub(
                download_name, download_link
            )

        files = {
            'urls': (None, download_link),
            'savepath': (None, target_folder),
            'category': (None, Constants.TORRENT_TAG)
        }

        try:
            self.ssn.post(
                f'{self.base_url}/api/v2/torrents/add',
                files=files
            )
            self.last_api_call = round(time())

        except RequestException:
            LOGGER.exception("Can't connect to qBittorrent instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        t_hash = download_link.split('urn:btih:')[1].split('&')[0].lower()
        self.statuses[t_hash] = None
        self.fail_timestamps[t_hash] = None
        self._update_statuses()
        return t_hash

    def get_download(self, download_id: str) -> Union[Dict[str, Any], None]:
        if self.last_update + Constants.TORRENT_UPDATE_INTERVAL < time():
            self._update_statuses()

        return self.statuses[download_id]

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        self._ensure_login()

        try:
            self.ssn.post(
                f'{self.base_url}/api/v2/torrents/delete',
                data={
                    'hashes': download_id,
                    'deleteFiles': delete_files
                }
            )
            self.last_api_call = round(time())

        except RequestException:
            LOGGER.exception("Can't connect to qBittorrent instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        del self.statuses[download_id]
        del self.fail_timestamps[download_id]
        return

    def on_shutdown(self) -> None:
        if self.last_api_call + self.login_timeout > round(time()):
            try:
                self.ssn.post(f'{self._base_url}/api/v2/auth/logout')

            except RequestException:
                LOGGER.exception("Can't connect to qBittorrent instance: ")
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)
        return

    @classmethod
    def test(
        cls,
        base_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        api_token: Union[str, None] = None
    ) -> None:
        cls._login(
            base_url,
            username,
            password
        )
        return
