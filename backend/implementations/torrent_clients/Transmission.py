# -*- coding: utf-8 -*-

from re import IGNORECASE, compile
from time import time
from typing import TYPE_CHECKING, Any, Dict, List, Union

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason,
                                      DownloadState, DownloadType)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_clients import BaseExternalClient
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from requests import Response

filename_magnet_link = compile(r'(?<=&dn=).*?(?=&)', IGNORECASE)


class Transmission(BaseExternalClient):
    client_type = 'Transmission'
    download_type = DownloadType.TORRENT

    required_tokens = ('title', 'base_url', 'username', 'password')

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

        self.ssn: Union[Session, None] = None
        self.torrent_hashes: Dict[str, Union[int, None]] = {}
        self.settings = Settings()
        return

    @classmethod
    def __api_request(
        cls,
        ssn: Session,
        base_url: str,
        method: str,
        arguments: Dict[str, Any],
        for_login: bool = False
    ) -> Response:
        """Make an API (RPC) request to a Transmission instance.

        Args:
            ssn (Session): The session to make the request with.
            base_url (str): Base URL of instance.
            method (str): The RPC method to execute.
            arguments (Dict[str, Any]): Any arguments to the method.
            for_login (bool, optional): When receiving a request to use a (new)
                session ID, do so but don't retry the original request afterwards.
                Needed when we want the original authentication request returned
                when logging in.
                Defaults to False.

        Raises:
            ClientNotWorking: _description_
            ClientNotWorking: _description_

        Returns:
            Response: _description_
        """
        try:
            response = ssn.post(
                f"{base_url}/transmission/rpc",
                json={
                    "method": method,
                    "arguments": arguments
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
            if not for_login:
                # Now that the Session ID is refreshed, try request again
                response = cls.__api_request(
                    ssn, base_url,
                    method, arguments,
                    for_login
                )

        return response

    @classmethod
    def _login(
        cls,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None]
    ) -> Session:
        """Login into a Transmission instance.

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
            method="session-get",
            arguments={},
            for_login=True
        )

        if auth_request.status_code == 409:
            # Success
            return ssn

        elif auth_request.ok:
            # Already logged in
            return ssn

        elif auth_request.status_code in (401, 403):
            LOGGER.error(
                f"Failed to authenticate for Transmission instance: {auth_request.text}"
            )
            raise CredentialInvalid

        else:
            LOGGER.error(
                f"Not connected to Transmission instance: {auth_request.text}"
            )
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

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

        args = {
            "filename": download_link,
            "paused": False,
            "download-dir": target_folder
        }

        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        result = self.__api_request(
            self.ssn, self.base_url,
            method="torrent-add",
            arguments=args
        ).json()["arguments"]

        added = result.get("torrent-added") or result.get("torrent-duplicate")
        t_hash = added.get("hashString")
        self.torrent_hashes[t_hash] = None
        return t_hash

    def get_download(self, download_id: str) -> Union[dict, None]:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        fields = [
            "hashString", "totalSize", "percentDone", "rateDownload",
            "status", "error", "errorString", "peersGettingFromUs"
        ]

        torrents: List[Dict[str, Any]] = self.__api_request(
            self.ssn,
            self.base_url,
            method="torrent-get",
            arguments={
                "ids": [download_id],
                "fields": fields
            }
        ).json()["arguments"].get("torrents", [])

        if not torrents:
            if download_id in self.torrent_hashes:
                return None
            else:
                return {}

        torrent = torrents[0]

        status = torrent.get("status", 0)
        dlspeed = torrent.get("rateDownload", 0)

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
            # Torrent is potentially failing
            if self.torrent_hashes[download_id] is None:
                self.torrent_hashes[download_id] = round(time())
                state = DownloadState.DOWNLOADING_STATE

            else:
                timeout = self.settings.sv.failing_download_timeout
                if timeout and (
                    time() - (self.torrent_hashes[download_id] or 0)
                    > timeout
                ):
                    state = DownloadState.FAILED_STATE
        else:
            self.torrent_hashes[download_id] = None

        return {
            'size': int(torrent.get('totalSize', 0)),
            'progress': round(torrent["percentDone"] * 100.0, 2),
            'speed': dlspeed,
            'state': state
        }

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        self.__api_request(
            self.ssn, self.base_url,
            method="torrent-remove",
            arguments={
                "ids": [download_id],
                "delete-local-data": delete_files
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
    ) -> None:
        Transmission._login(
            base_url,
            username,
            password
        )
        return
