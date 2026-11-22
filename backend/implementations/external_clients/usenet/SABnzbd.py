# -*- coding: utf-8 -*-

"""
SABnzbd external download client (usenet).
"""

from os.path import join, normpath
from time import time
from typing import Any, Dict, List, Union

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason, Constants,
                                      DownloadState, DownloadType,
                                      ExternalClientField as ECF)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_client_manager import (
    BaseExternalClient, ExternalClients)

QUEUE_STATE_MAPPING = {
    "Queued": DownloadState.QUEUED_STATE,
    "Grabbing": DownloadState.QUEUED_STATE,
    "Fetching": DownloadState.QUEUED_STATE,
    "Propagating": DownloadState.QUEUED_STATE,
    "Paused": DownloadState.PAUSED_STATE,
    "Downloading": DownloadState.DOWNLOADING_STATE,
    "Checking": DownloadState.DOWNLOADING_STATE,
}
"SABnzbd queue slot status to download state"

HISTORY_DONE = "Completed"
HISTORY_FAILED = "Failed"
"""
Final SABnzbd history statuses. Any other history status (Verifying,
Repairing, Extracting, Moving, Running, ...) means SABnzbd is still
post-processing the download.
"""


@ExternalClients.register_client(
    DownloadType.USENET, 'SABnzbd',
    (ECF.TITLE, ECF.ENABLED, ECF.BASE_URL, ECF.API_TOKEN)
)
class SABnzbd(BaseExternalClient):
    def __init__(self, client_id: int) -> None:
        super().__init__(client_id)
        self.ssn = Session()
        self.last_update: float = 0.0
        self.statuses: Dict[str, Union[Dict[str, Any], None]] = {}
        return

    # region API
    @staticmethod
    def _api(
        ssn: Session,
        base_url: str,
        api_token: Union[str, None],
        quiet: bool = False,
        **params: Any
    ) -> Dict[str, Any]:
        """Make a request to the SABnzbd API.

        Args:
            ssn (Session): The session to make the request with.
            base_url (str): Base URL of the instance.
            api_token (Union[str, None]): The API key of the instance.
            quiet (bool, optional): Don't log an error that SABnzbd returns.
                Defaults to False.
            params (kwargs): The parameters of the API call (mode, name, ...).

        Raises:
            ClientNotWorking: Can't connect to client or client returned
                unexpected result.
            CredentialInvalid: The API key is invalid.

        Returns:
            Dict[str, Any]: The JSON response.
        """
        try:
            response = ssn.get(
                f"{base_url}/api",
                params={
                    **params,
                    'apikey': api_token or '',
                    'output': 'json'
                }
            )
        except RequestException:
            LOGGER.exception("Can't connect to SABnzbd instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if 'api key' in response.text[:200].lower():
            # SABnzbd answers a wrong key with "API Key Incorrect" (or
            # "API Key Required"), as plain text with a 403 or as JSON
            raise CredentialInvalid

        if response.status_code in (401, 403):
            raise ClientNotWorking(BrokenClientReason.ACCESS_DENIED)

        try:
            result = response.json()
        except ValueError:
            # E.g. SABnzbd's hostname verification answers with a HTML page
            LOGGER.error(
                f"Not connected to SABnzbd instance: {response.text[:200]}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        if isinstance(result, dict) and result.get('status') is False:
            error = str(result.get('error', ''))
            if 'api key' in error.lower():
                raise CredentialInvalid
            if not quiet:
                LOGGER.error(f"SABnzbd returned an error: {error}")
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        return result

    def __call(self, quiet: bool = False, **params: Any) -> Dict[str, Any]:
        return self._api(
            self.ssn, self._base_url, self._api_token, quiet, **params
        )

    def _category_for_folder(self, target_folder: str) -> Union[str, None]:
        """Find the SABnzbd category that downloads into the given folder.

        Args:
            target_folder (str): The folder (as SABnzbd sees it) that the
                download should end up in.

        Returns:
            Union[str, None]: The name of the category, or `None` to use the
                default category.
        """
        try:
            config = self.__call(mode='get_config')['config']
        except (ClientNotWorking, CredentialInvalid, KeyError):
            return None

        complete_dir = config.get('misc', {}).get('complete_dir', '')
        target = normpath(target_folder)
        for category in config.get('categories', []):
            name = category.get('name')
            folder = category.get('dir') or ''
            if not name or name == '*' or not folder:
                continue
            path = folder if folder.startswith('/') else join(
                complete_dir, folder
            )
            if normpath(path) == target:
                return name

        LOGGER.warning(
            "No SABnzbd category downloads into %s, using the default "
            "category. Add a category with that folder in SABnzbd, so "
            "Kapowarr finds the downloads.",
            target_folder
        )
        return None

    def find_download(self, download_name: str) -> Union[str, None]:
        """Find a download in the queue or history by its name.

        Args:
            download_name (str): The name the download was added with.

        Returns:
            Union[str, None]: The nzo_id of the download, if found.
        """
        for slot in self.__call(mode='queue', search=download_name)\
                .get('queue', {}).get('slots', []):
            if slot.get('filename') == download_name:
                return slot.get('nzo_id')

        for slot in self.__call(mode='history', search=download_name)\
                .get('history', {}).get('slots', []):
            if slot.get('name') == download_name:
                return slot.get('nzo_id')

        return None

    def _update_statuses(self) -> None:
        ids: List[str] = list(self.statuses)
        if not ids:
            self.last_update = time()
            return

        queue = self.__call(mode='queue', nzo_ids=','.join(ids))\
            .get('queue', {})
        speed = float(queue.get('kbpersec') or 0) * 1024
        in_queue: Dict[str, Dict[str, Any]] = {
            slot['nzo_id']: slot
            for slot in queue.get('slots', [])
        }

        missing = [i for i in ids if i not in in_queue]
        in_history: Dict[str, Dict[str, Any]] = {}
        if missing:
            in_history = {
                slot['nzo_id']: slot
                for slot in self.__call(
                    mode='history', nzo_ids=','.join(missing)
                ).get('history', {}).get('slots', [])
            }

        for nzo_id in ids:
            if nzo_id in in_queue:
                slot = in_queue[nzo_id]
                state = QUEUE_STATE_MAPPING.get(
                    slot.get('status', ''),
                    DownloadState.DOWNLOADING_STATE
                )
                self.statuses[nzo_id] = {
                    'size': int(float(slot.get('mb') or 0) * 1024 * 1024),
                    'progress': float(slot.get('percentage') or 0),
                    'speed': (
                        speed
                        if state == DownloadState.DOWNLOADING_STATE
                        else 0.0
                    ),
                    'state': state,
                    'storage': None
                }

            elif nzo_id in in_history:
                slot = in_history[nzo_id]
                status = slot.get('status', '')
                if status == HISTORY_DONE:
                    state = DownloadState.IMPORTING_STATE
                elif status == HISTORY_FAILED:
                    LOGGER.warning(
                        "SABnzbd download %s failed: %s",
                        nzo_id, slot.get('fail_message', '')
                    )
                    state = DownloadState.FAILED_STATE
                else:
                    # Still post-processing (repairing, unpacking, ...)
                    state = DownloadState.DOWNLOADING_STATE

                self.statuses[nzo_id] = {
                    'size': int(slot.get('bytes') or 0),
                    'progress': 100.0,
                    'speed': 0.0,
                    'state': state,
                    'storage': slot.get('storage') or None
                }

            else:
                # Removed from SABnzbd
                self.statuses[nzo_id] = None

        self.last_update = time()
        return

    # region Client
    def add_download(
        self,
        download_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        if download_name:
            existing = self.find_download(download_name)
            if existing:
                LOGGER.info(
                    "Download %s already in SABnzbd as %s",
                    download_name, existing
                )
                self.statuses[existing] = None
                self._update_statuses()
                return existing

        params: Dict[str, Any] = {
            'mode': 'addurl',
            'name': download_link
        }
        if download_name:
            params['nzbname'] = download_name
        category = self._category_for_folder(target_folder)
        if category:
            params['cat'] = category

        result = self.__call(**params)
        nzo_ids = result.get('nzo_ids') or []
        if not nzo_ids:
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        nzo_id: str = nzo_ids[0]
        self.statuses[nzo_id] = None
        self._update_statuses()
        return nzo_id

    def get_download(self, download_id: str) -> Union[Dict[str, Any], None]:
        if (
            download_id not in self.statuses
            or self.last_update + Constants.EXTERNAL_CLIENT_UPDATE_INTERVAL
                < time()
        ):
            self.statuses.setdefault(download_id, None)
            self._update_statuses()
        return self.statuses[download_id]

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        # The job is either in the queue or in the history. SABnzbd answers
        # with an error for the list it isn't in (and for a job that's already
        # gone), so try both. Only a connection problem is a real failure.
        del_files = 1 if delete_files else 0
        for mode in ('queue', 'history'):
            try:
                self.__call(
                    quiet=True,
                    mode=mode, name='delete',
                    value=download_id, del_files=del_files
                )
            except ClientNotWorking as e:
                if e.reason == BrokenClientReason.CONNECTION_ERROR:
                    raise

        self.statuses.pop(download_id, None)
        return

    def on_shutdown(self) -> None:
        self.ssn.close()
        return

    @classmethod
    def test(
        cls,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> None:
        with Session() as ssn:
            version = cls._api(ssn, base_url, api_token, mode='version')
            if 'version' not in version:
                raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

            # The version call works without API key, so check the key with
            # a call that needs it
            cls._api(ssn, base_url, api_token, mode='queue', limit=1)
        return
