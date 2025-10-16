# -*- coding: utf-8 -*-

from re import IGNORECASE, compile
from time import time
from typing import Any, Dict, List, Union

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import Constants, DownloadState, DownloadType
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_clients import BaseExternalClient
from backend.internals.settings import Settings


filename_magnet_link = compile(r'(?<=&dn=).*?(?=&)', IGNORECASE)


class Transmission(BaseExternalClient):
    client_type = 'Transmission'
    download_type = DownloadType.TORRENT

    # Matching qBittorrent's required tokens for consistency with settings UI
    required_tokens = ('title', 'base_url', 'username', 'password')

    # Transmission status codes:
    # 0: Stopped, 1: CheckWait, 2: Checking, 3: DownloadWait,
    # 4: Downloading, 5: SeedWait, 6: Seeding
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
        # Track stall/failure timing similar to qBittorrent.py
        self.torrent_hashes: Dict[str, Union[int, None]] = {}
        self.settings = Settings()
        self._rpc_url: Union[str, None] = None
        return

    @staticmethod
    def _ensure_session_id(ssn: Session, url: str, username: Union[str, None], password: Union[str, None]) -> None:
        """
        Establish a Transmission RPC session by performing a probe request
        to fetch X-Transmission-Session-Id (409 handshake), then store it
        in the session headers for subsequent calls.
        """
        if username and password:
            ssn.auth = (username, password)

        try:
            r = ssn.post(url, json={"method": "session-get", "arguments": {}}, headers={})
        except RequestException:
            LOGGER.exception("Can't connect to Transmission instance: ")
            raise ClientNotWorking()

        # Transmission returns 409 on first request with required Session-Id
        if r.status_code == 409:
            sid = r.headers.get('X-Transmission-Session-Id')
            if not sid:
                LOGGER.error("Transmission instance missing Session-Id header.")
                raise ClientNotWorking()
            ssn.headers.update({'X-Transmission-Session-Id': sid})
            return

        # 401/403 typically indicate auth issues
        if r.status_code in (401, 403):
            LOGGER.error(f"Failed to authenticate with Transmission instance: HTTP {r.status_code}")
            raise CredentialInvalid

        if not r.ok:
            LOGGER.error(f"Not connected to Transmission instance: HTTP {r.status_code} {r.text}")
            raise ClientNotWorking()

        # If OK right away, we may have already had a valid Session-Id (reverse proxy, etc.)
        sid = r.headers.get('X-Transmission-Session-Id')
        if sid:
            ssn.headers.update({'X-Transmission-Session-Id': sid})

    def _login(self, base_url: str, username: Union[str, None], password: Union[str, None]) -> Session:
        """
        Prepare a requests Session for Transmission RPC usage.
        """
        ssn = Session()
        rpc_url = f'{base_url}/transmission/rpc'
        self._ensure_session_id(ssn, rpc_url, username, password)
        self._rpc_url = rpc_url
        return ssn

    def _rpc(self, method: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a Transmission RPC call with Session-Id retry logic.
        """
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        assert self._rpc_url is not None
        try:
            r = self.ssn.post(self._rpc_url, json={"method": method, "arguments": arguments})
        except RequestException:
            LOGGER.exception("Transmission RPC connection error: ")
            raise ClientNotWorking()

        if r.status_code == 409:
            # Refresh Session-Id and retry once
            sid = r.headers.get('X-Transmission-Session-Id')
            if not sid:
                LOGGER.error("Transmission 409 without Session-Id header.")
                raise ClientNotWorking()
            self.ssn.headers.update({'X-Transmission-Session-Id': sid})
            r = self.ssn.post(self._rpc_url, json={"method": method, "arguments": arguments})

        if r.status_code in (401, 403):
            LOGGER.error(f"Failed to authenticate with Transmission instance during RPC: HTTP {r.status_code}")
            raise CredentialInvalid

        if not r.ok:
            LOGGER.error(f"Transmission RPC failed: HTTP {r.status_code} {r.text}")
            raise ClientNotWorking()

        data = r.json()
        if data.get("result") != "success":
            # Transmission returns result strings like 'success', 'duplicate torrent', etc.
            # Treat non-success as a client error
            LOGGER.error(f"Transmission RPC error: {data.get('result')}")
            raise ClientNotWorking()
        return data.get("arguments", {})

    def add_download(
        self,
        download_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        if download_name is not None:
            download_link = filename_magnet_link.sub(download_name, download_link)

        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        args = {
            "filename": download_link,
            "paused": False
        }
        # Transmission uses "download-dir" for target folder
        if target_folder:
            args["download-dir"] = target_folder

        result = self._rpc("torrent-add", args)

        # Response can be either 'torrent-added' or 'torrent-duplicate'
        added = result.get("torrent-added") or result.get("torrent-duplicate")
        if not added:
            LOGGER.error(f"Transmission did not return torrent-added/duplicate for link: {download_link}")
            raise ClientNotWorking()

        t_hash = added.get("hashString")
        if not t_hash:
            # Fallback: parse from magnet if provided
            try:
                t_hash = download_link.split('urn:btih:')[1].split('&')[0]
            except Exception:
                LOGGER.error("Unable to determine torrent hash.")
                raise ClientNotWorking()

        self.torrent_hashes[t_hash] = None
        return t_hash

    def get_download(self, download_id: str) -> Union[dict, None]:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        # Fetch by hashString
        fields = [
            "hashString", "totalSize", "percentDone", "rateDownload",
            "status", "error", "errorString", "peersGettingFromUs"
        ]
        args = {"ids": [download_id], "fields": fields}
        torrents: List[Dict[str, Any]] = self._rpc("torrent-get", args).get("torrents", [])

        if not torrents:
            # Align behavior with qBittorrent.py:
            # None => not found *yet* but previously added (treat as "still adding"),
            # {} => hard not-found if we never tracked it
            if download_id in self.torrent_hashes:
                return None
            else:
                return {}

        t = torrents[0]

        # Error handling from Transmission: non-zero 'error' indicates a failure
        if t.get("error", 0):
            state = DownloadState.FAILED_STATE
        else:
            state = self.state_mapping.get(t.get("status", 0), DownloadState.IMPORTING_STATE)

        # Stall/failing logic similar to qBittorrent:
        # Treat prolonged checking/waiting or "downloading with zero rate" as potential failure
        status = int(t.get("status", 0))
        dlspeed = int(t.get("rateDownload", 0))

        potential_stall = (
            status in (1, 2, 3)  # CheckWait, Checking, DownloadWait
            or (status == 4 and dlspeed == 0)  # Downloading but zero rate
        )

        if potential_stall and state not in (DownloadState.FAILED_STATE, DownloadState.SEEDING_STATE):
            if self.torrent_hashes.get(download_id) is None:
                self.torrent_hashes[download_id] = round(time())
                state = DownloadState.DOWNLOADING_STATE
            else:
                timeout = self.settings.sv.failing_download_timeout
                if timeout and (time() - (self.torrent_hashes[download_id] or 0) > timeout):
                    state = DownloadState.FAILED_STATE
        else:
            self.torrent_hashes[download_id] = None

        progress_pct = round(float(t.get("percentDone", 0.0)) * 100.0, 2)

        return {
            'size': int(t.get('totalSize', 0)),
            'progress': progress_pct,
            'speed': dlspeed,
            'state': state
        }

    def delete_download(self, download_id: str, delete_files: bool) -> None:
        if not self.ssn:
            self.ssn = self._login(self.base_url, self.username, self.password)

        self._rpc("torrent-remove", {
            "ids": [download_id],
            "delete-local-data": bool(delete_files)
        })
        if download_id in self.torrent_hashes:
            del self.torrent_hashes[download_id]
        return

    @staticmethod
    def test(
        base_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        api_token: Union[str, None] = None
    ) -> None:
        # Verify connectivity and auth by fetching a session and calling session-get
        ssn = Session()
        rpc_url = f'{base_url}/transmission/rpc'
        if username and password:
            ssn.auth = (username, password)

        try:
            r = ssn.post(rpc_url, json={"method": "session-get", "arguments": {}}, headers={})
        except RequestException:
            LOGGER.exception("Can't connect to Transmission instance: ")
            raise ClientNotWorking()

        if r.status_code == 409:
            sid = r.headers.get('X-Transmission-Session-Id')
            if not sid:
                raise ClientNotWorking()
            ssn.headers.update({'X-Transmission-Session-Id': sid})
            r = ssn.post(rpc_url, json={"method": "session-get", "arguments": {}})

        if r.status_code in (401, 403):
            raise CredentialInvalid

        if not r.ok:
            raise ClientNotWorking()

        data = r.json()
        if data.get("result") != "success":
            raise ClientNotWorking()
        return
