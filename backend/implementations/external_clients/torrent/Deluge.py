# -*- coding: utf-8 -*-

from time import time
from typing import Any, Dict, List, Union

from requests import Response
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
    DownloadType.TORRENT, 'Deluge',
    (ECF.TITLE, ECF.ENABLED, ECF.BASE_URL, ECF.PASSWORD)
)
class Deluge(BaseExternalClient):
    state_mapping = {
        'Queued': DownloadState.QUEUED_STATE,
        'Paused': DownloadState.PAUSED_STATE,
        'Checking': DownloadState.DOWNLOADING_STATE,
        'Allocating': DownloadState.DOWNLOADING_STATE,
        'Downloading': DownloadState.DOWNLOADING_STATE,
        'Seeding': DownloadState.SEEDING_STATE,
        'Queued Seed': DownloadState.SEEDING_STATE,
        'Error': DownloadState.FAILED_STATE,
        'Moving': DownloadState.IMPORTING_STATE
    }

    def __init__(self, client_id: int) -> None:
        super().__init__(client_id)

        self.ssn = self._login(self._base_url, self._password)
        self.last_update: float = 0.0
        self.statuses: Dict[str, Union[Dict[str, Any], None]] = {}
        self.fail_timestamps: Dict[str, Union[int, None]] = {}
        self.settings = Settings()
        return

    @classmethod
    def __api_request(
        cls,
        ssn: Session,
        base_url: str,
        method: str,
        params: List[Any]
    ) -> Any:
        try:
            response: Response = ssn.post(
                f'{base_url}/json',
                json={
                    'method': method,
                    'params': params,
                    'id': 1
                }
            )

        except RequestException:
            LOGGER.exception("Can't connect to Deluge instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.status_code in (401, 403):
            LOGGER.error(
                f"Failed to authenticate for Deluge instance: {response.text}"
            )
            raise CredentialInvalid

        if response.status_code == 404:
            LOGGER.error(
                f"Can't connect or version too low of Deluge instance: {response.text}"
            )
            raise ClientNotWorking(BrokenClientReason.VERSION_NOT_SUPPORTED)

        if not response.ok:
            LOGGER.error(
                f"Not connected to Deluge instance: {response.text}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        try:
            data = response.json()
        except ValueError:
            LOGGER.error(
                f"Deluge instance returned a non-JSON response: {response.text}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        if not isinstance(data, dict) or 'result' not in data:
            LOGGER.error(
                f"Deluge instance returned an unexpected response: {data}"
            )
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        return data['result']

    @classmethod
    def _login(cls, base_url: str, password: Union[str, None]) -> Session:
        ssn = Session()

        authenticated = cls.__api_request(
            ssn, base_url,
            method='auth.login',
            params=[password or '']
        )
        if authenticated is not True:
            LOGGER.error("Failed to authenticate for Deluge instance")
            raise CredentialInvalid

        return ssn

    def _update_statuses(self) -> None:
        if not self.statuses:
            self.last_update = time()
            return

        fields = [
            'total_size', 'progress', 'download_payload_rate', 'state'
        ]
        torrents = self.__api_request(
            self.ssn, self._base_url,
            method='core.get_torrents_status',
            params=[{}, fields]
        )
        if not isinstance(torrents, dict):
            LOGGER.error(
                f"Deluge returned invalid torrent statuses: {torrents}"
            )
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        for t_hash in self.statuses:
            torrent = torrents.get(t_hash)
            if not isinstance(torrent, dict):
                self.statuses[t_hash] = None
                self.fail_timestamps[t_hash] = None
                continue

            deluge_state = torrent.get('state', '')
            speed = int(torrent.get('download_payload_rate', 0))
            state = self.state_mapping.get(
                deluge_state,
                DownloadState.IMPORTING_STATE
            )

            potential_stall = (
                deluge_state in ('Checking', 'Allocating')
                or (deluge_state == 'Downloading' and speed == 0)
            )
            if potential_stall and state not in (
                DownloadState.FAILED_STATE,
                DownloadState.SEEDING_STATE
            ):
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
                'size': int(torrent.get('total_size', 0)),
                'progress': round(float(torrent.get('progress', 0)), 2),
                'speed': speed,
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
        if download_name is not None:
            download_link = filename_magnet_link.sub(
                download_name, download_link
            )

        method = (
            'core.add_torrent_magnet'
            if download_link.startswith('magnet:')
            else 'core.add_torrent_url'
        )
        t_hash = self.__api_request(
            self.ssn, self._base_url,
            method=method,
            params=[
                download_link,
                {
                    'download_location': target_folder,
                    'add_paused': False
                }
            ]
        )
        if not isinstance(t_hash, str) or not t_hash:
            LOGGER.error(f"Deluge returned an invalid torrent ID: {t_hash}")
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        self.statuses[t_hash] = None
        self.fail_timestamps[t_hash] = None
        self._update_statuses()
        return t_hash

    def get_download(self, download_id: str) -> Union[Dict[str, Any], None]:
        if self.last_update + Constants.EXTERNAL_CLIENT_UPDATE_INTERVAL < time():
            self._update_statuses()

        return self.statuses[download_id]

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        self.__api_request(
            self.ssn, self._base_url,
            method='core.remove_torrent',
            params=[download_id, delete_files]
        )
        del self.statuses[download_id]
        del self.fail_timestamps[download_id]
        return

    def on_shutdown(self) -> None:
        try:
            self.__api_request(
                self.ssn, self._base_url,
                method='auth.delete_session',
                params=[]
            )
        finally:
            self.ssn.close()
        return

    @classmethod
    def test(
        cls,
        base_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        api_token: Union[str, None] = None
    ) -> None:
        ssn = cls._login(base_url, password)
        ssn.close()
        return
