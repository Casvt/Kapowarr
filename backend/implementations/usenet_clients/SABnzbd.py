# -*- coding: utf-8 -*-

from time import time
from typing import Any, Dict, Union

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason,
                                      DownloadState, DownloadType)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_clients import BaseExternalClient
from backend.internals.settings import Settings


class SABnzbd(BaseExternalClient):
    client_type = 'SABnzbd'
    download_type = DownloadType.USENET

    required_tokens = ('title', 'base_url', 'api_token')

    state_mapping = {
        'Queued': DownloadState.QUEUED_STATE,
        'Paused': DownloadState.PAUSED_STATE,
        'Downloading': DownloadState.DOWNLOADING_STATE,
        'Extracting': DownloadState.IMPORTING_STATE,
        'Moving': DownloadState.IMPORTING_STATE,
        'Running': DownloadState.DOWNLOADING_STATE,
        'Propagating': DownloadState.DOWNLOADING_STATE,
        'Verifying': DownloadState.DOWNLOADING_STATE,
        'Repairing': DownloadState.DOWNLOADING_STATE,
        'Fetching': DownloadState.DOWNLOADING_STATE,
        'Failed': DownloadState.FAILED_STATE,
        'Completed': DownloadState.SEEDING_STATE
    }

    def __init__(self, client_id: int) -> None:
        super().__init__(client_id)

        self.ssn: Union[Session, None] = None
        self.nzb_ids: Dict[str, Union[int, None]] = {}
        self.settings = Settings()
        return

    @staticmethod
    def _login(
        base_url: str,
        api_token: Union[str, None]
    ) -> Session:
        """Test connection to SABnzbd instance.

        Args:
            base_url (str): Base URL of instance.
            api_token (Union[str, None]): API token to access client.

        Raises:
            ClientNotWorking: Can't connect to client.
            CredentialInvalid: API token is invalid.

        Returns:
            Session: Request session configured for SABnzbd.
        """
        ssn = Session()

        try:
            response = ssn.get(
                f'{base_url}/api',
                params={
                    'mode': 'version',
                    'apikey': api_token,
                    'output': 'json'
                }
            )

        except RequestException:
            LOGGER.exception("Can't connect to SABnzbd instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if not response.ok:
            LOGGER.error(
                f"Can't connect to SABnzbd instance: {response.text}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        try:
            result = response.json()
        except Exception:
            LOGGER.error(
                f"Not connected to SABnzbd instance: Invalid JSON response"
            )
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE)

        if result.get('error'):
            if 'API Key Incorrect' in result.get('error', ''):
                LOGGER.error(
                    f"Failed to authenticate for SABnzbd instance: {
                        result.get('error')}")
                raise CredentialInvalid
            else:
                LOGGER.error(
                    f"Not connected to SABnzbd instance: {result.get('error')}"
                )
                raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        return ssn

    def add_download(
        self,
        download_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.api_token)

        params = {
            'mode': 'addurl',
            'apikey': self.api_token,
            'output': 'json',
            'name': download_link,
            'cat': 'kapowarr'
        }

        if download_name:
            params['nzbname'] = download_name

        try:
            response = self.ssn.get(
                f'{self.base_url}/api',
                params=params
            )
            result = response.json()

            if result.get('status') is False:
                LOGGER.error(
                    f"Failed to add NZB to SABnzbd: {
                        result.get(
                            'error',
                            'Unknown error')}")
                raise ClientNotWorking(
                    BrokenClientReason.FAILED_PROCESSING_RESPONSE)

            nzb_id = result.get('nzo_ids', [''])[0]
            if not nzb_id:
                raise ClientNotWorking(
                    BrokenClientReason.FAILED_PROCESSING_RESPONSE)

            self.nzb_ids[nzb_id] = None
            return nzb_id

        except (RequestException, KeyError, IndexError) as e:
            LOGGER.exception("Failed to add download to SABnzbd: ")
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE)

    def get_download(self, download_id: str) -> Union[dict, None]:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.api_token)

        try:
            response = self.ssn.get(
                f'{self.base_url}/api',
                params={
                    'mode': 'queue',
                    'apikey': self.api_token,
                    'output': 'json'
                }
            )
            queue_data = response.json()

            # Check queue for the download
            for slot in queue_data.get('queue', {}).get('slots', []):
                if slot.get('nzo_id') == download_id:
                    return self._parse_download_status(slot, 'queue')

            # Check history if not in queue
            response = self.ssn.get(
                f'{self.base_url}/api',
                params={
                    'mode': 'history',
                    'apikey': self.api_token,
                    'output': 'json'
                }
            )
            history_data = response.json()

            for slot in history_data.get('history', {}).get('slots', []):
                if slot.get('nzo_id') == download_id:
                    return self._parse_download_status(slot, 'history')

            # Download not found
            if download_id in self.nzb_ids:
                return None
            else:
                return {}

        except (RequestException, KeyError) as e:
            LOGGER.exception("Failed to get download status from SABnzbd: ")
            return {}

    def _parse_download_status(
        self,
        slot: Dict[str, Any],
        source: str
    ) -> Dict[str, Any]:
        """Parse download status from SABnzbd slot data.

        Args:
            slot (Dict[str, Any]): The slot data from SABnzbd.
            source (str): Whether from 'queue' or 'history'.

        Returns:
            Dict[str, Any]: Normalized download status.
        """
        if source == 'queue':
            status = slot.get('status', 'Unknown')
            size_mb = float(slot.get('mb', 0))
            size_left_mb = float(slot.get('mbleft', 0))
            speed_bytes = int(float(slot.get('mb/s', 0)) * 1024 * 1024)

            size = int(size_mb * 1024 * 1024)
            if size > 0 and size_left_mb >= 0:
                progress = round(((size_mb - size_left_mb) / size_mb) * 100, 2)
            else:
                progress = 0.0

            state = self.state_mapping.get(
                status, DownloadState.DOWNLOADING_STATE)

        else:  # history
            status = slot.get('status', 'Unknown')
            size = int(float(slot.get('bytes', 0)))
            speed_bytes = 0

            # Check if failed
            if status == 'Failed':
                state = DownloadState.FAILED_STATE
                progress = 0.0
            else:
                state = DownloadState.SEEDING_STATE
                progress = 100.0

        # Check for potential stall
        download_id = slot.get('nzo_id', '')
        if state == DownloadState.DOWNLOADING_STATE and speed_bytes == 0:
            if self.nzb_ids.get(download_id) is None:
                self.nzb_ids[download_id] = round(time())
            else:
                timeout = self.settings.sv.failing_download_timeout
                if timeout and (
                    time() - (self.nzb_ids[download_id] or 0) > timeout
                ):
                    state = DownloadState.FAILED_STATE
        else:
            self.nzb_ids[download_id] = None

        return {
            'size': size,
            'progress': progress,
            'speed': speed_bytes,
            'state': state
        }

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.api_token)

        # Try to delete from queue first
        self.ssn.get(
            f'{self.base_url}/api',
            params={
                'mode': 'queue',
                'name': 'delete',
                'apikey': self.api_token,
                'value': download_id,
                'del_files': '1' if delete_files else '0'
            }
        )

        # Also try to delete from history
        self.ssn.get(
            f'{self.base_url}/api',
            params={
                'mode': 'history',
                'name': 'delete',
                'apikey': self.api_token,
                'value': download_id,
                'del_files': '1' if delete_files else '0'
            }
        )

        if download_id in self.nzb_ids:
            del self.nzb_ids[download_id]
        return

    @staticmethod
    def test(
        base_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        api_token: Union[str, None] = None
    ) -> None:
        SABnzbd._login(base_url, api_token)
        return
