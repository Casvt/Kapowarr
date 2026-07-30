# -*- coding: utf-8 -*-

from random import randint
from time import time
from typing import Any, Dict, Union

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
    DownloadType.TORRENT, 'Transmission',
    (ECF.TITLE, ECF.ENABLED, ECF.BASE_URL, ECF.USERNAME, ECF.PASSWORD)
)
class Transmission(BaseExternalClient):
    state_mapping = {
        0: DownloadState.PAUSED_STATE,        # Stopped
        1: DownloadState.DOWNLOADING_STATE,   # CheckWait
        2: DownloadState.DOWNLOADING_STATE,   # Checking
        3: DownloadState.QUEUED_STATE,        # DownloadWait
        4: DownloadState.DOWNLOADING_STATE,   # Downloading
        5: DownloadState.SEEDING_STATE,       # SeedWait (queued seeding)
        6: DownloadState.SEEDING_STATE        # Seeding
    }

    def __init__(self, client_id: int) -> None:
        super().__init__(client_id)

        self.ssn: Session = self._login(
            self._base_url, self._username, self._password
        )
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
        params: Dict[str, Any]
    ) -> Response:
        """Make an API (RPC) request to a Transmission instance.

        Args:
            ssn (Session): The session to make the request with.
            base_url (str): Base URL of instance.
            method (str): The RPC method to execute.
            params (Dict[str, Any]): Any arguments to the method.

        Raises:
            ClientNotWorking: Can't connect to client or client returned
                unexpected result.

        Returns:
            Response: The server response to the request.
        """
        try:
            response = ssn.post(
                f"{base_url}/transmission/rpc",
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": randint(1, 1_000_000)
                }
            )

        except RequestException:
            LOGGER.exception("Can't connect to Transmission instance: ")
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.status_code == 409:
            # We need to set the Session ID
            sid = response.headers.get('X-Transmission-Session-Id')
            if not sid:
                raise ClientNotWorking(
                    BrokenClientReason.FAILED_PROCESSING_RESPONSE
                )

            ssn.headers.update({'X-Transmission-Session-Id': sid})

            # Now that the Session ID is refreshed, try request again
            response = cls.__api_request(
                ssn, base_url,
                method, params
            )

        return response

    @classmethod
    def _login(
        cls,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None]
    ) -> Session:
        """Login into Transmission client.

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

        if username and password:
            ssn.auth = (username, password)

        auth_request = cls.__api_request(
            ssn, base_url,
            method="session_get",
            params={
                "fields": ["rpc_version_semver"]
            }
        )

        if auth_request.status_code in (401, 403):
            LOGGER.error(
                f"Failed to authenticate for Transmission instance: {auth_request.text}"
            )
            raise CredentialInvalid

        elif not auth_request.ok:
            LOGGER.error(
                f"Not connected to Transmission instance: {auth_request.text}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        rpc_version_semver = tuple(
            int(i)
            for i in auth_request.json()["result"][
                "rpc_version_semver"
            ].split(".")
        )
        if rpc_version_semver < (6, 0, 0):
            # Should be at least v4.1.0 (rpc_version_semver 6.0.0)
            raise ClientNotWorking(BrokenClientReason.VERSION_NOT_SUPPORTED)

        return ssn

    def _update_statuses(self) -> None:
        fields = [
            "hash_string", "total_size", "percent_done", "rate_download",
            "status", "error", "error_string", "peers_getting_from_us"
        ]

        torrents: Dict[str, Dict[str, Any]] = {
            torrent["hash_string"]: torrent
            for torrent in self.__api_request(
                self.ssn,
                self._base_url,
                method="torrent_get",
                params={
                    "ids": list(self.statuses),
                    "fields": fields
                }
            ).json()["result"].get("torrents", [])
        }

        for t_hash in self.statuses:
            if t_hash not in torrents:
                self.statuses[t_hash] = None

            torrent = torrents[t_hash]

            status = torrent.get("status", 0)
            dlspeed = torrent.get("rate_download", 0)

            if torrent.get("error", 0):
                state = DownloadState.FAILED_STATE
            else:
                state = self.state_mapping.get(
                    torrent.get("status", 0),
                    DownloadState.IMPORTING_STATE
                )

            potential_stall = (
                status in (1, 2, 3)  # CheckWait, Checking, DownloadWait
                or (status == 4 and dlspeed == 0)  # Downloading but zero rate
            )

            if potential_stall and state not in (
                DownloadState.FAILED_STATE,
                DownloadState.SEEDING_STATE
            ):
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
                'size': int(torrent.get('total_size', 0)),
                'progress': round(torrent["percent_done"] * 100.0, 2),
                'speed': dlspeed,
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

        result = self.__api_request(
            self.ssn, self._base_url,
            method="torrent_add",
            params={
                "filename": download_link,
                "paused": False,
                "download_dir": target_folder
            }
        ).json()["result"]

        added = result.get("torrent_added") or result.get("torrent_duplicate")
        t_hash = added.get("hash_string")
        self.statuses[t_hash] = None
        self.fail_timestamps[t_hash] = None
        self._update_statuses()
        return t_hash

    def get_download(self, download_id: str) -> Union[dict, None]:
        if self.last_update + Constants.EXTERNAL_CLIENT_UPDATE_INTERVAL < time():
            self._update_statuses()

        return self.statuses[download_id]

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        self.__api_request(
            self.ssn, self._base_url,
            method="torrent_remove",
            params={
                "ids": [download_id],
                "delete_local_data": delete_files
            }
        )

        del self.statuses[download_id]
        del self.fail_timestamps[download_id]
        return

    def on_shutdown(self) -> None:
        self.__api_request(
            self.ssn, self._base_url,
            method="session_close",
            params={}
        )
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
