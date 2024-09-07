# -*- coding: utf-8 -*-

"""
Clients for downloading a torrent using a torrent client
"""

from os.path import join
from typing import Dict, List, Type, Union

from requests import RequestException

from backend.custom_exceptions import (InvalidKeyValue, LinkBroken,
                                       TorrentClientNotFound,
                                       TorrentClientNotWorking)
from backend.db import get_db
from backend.download_general import BaseTorrentClient, ExternalDownload
from backend.enums import BlocklistReason, DownloadSource, DownloadState
from backend.helpers import ClientTestResult, Session, get_torrent_info
from backend.logging import LOGGER
from backend.settings import Settings
from backend.torrent_clients import qBittorrent

# =====================
# Managing clients
# =====================

client_types: Dict[str, Type[BaseTorrentClient]] = {
    'qBittorrent': qBittorrent.qBittorrent
}


class TorrentClients:
    @staticmethod
    def test(
        type: str,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> ClientTestResult:
        """Test if a client is supported, working and available

        Args:
            type (str): The client identifier.
                A key from `download_torrent_clients.client_types`.

            base_url (str): The base url that Kapowarr needs to connect to the client

            username (Union[str, None]): The username to use when authenticating to the client.
                Allowed to be `None` if not applicable.

            password (Union[str, None]): The password to use when authenticating to the client.
                Allowed to be `None` if not applicable.

            api_token (Union[str, None]): The api token to use when authenticating to the client.
                Allowed to be `None` if not applicable.

        Raises:
            InvalidKeyValue: One of the parameters has an invalid argument

        Returns:
            ClientTestResult: Whether or not the test was successful or not
        """
        if type not in client_types:
            raise InvalidKeyValue('type', type)

        base_url = base_url.rstrip('/')
        if not base_url.startswith(('http://', 'https://')):
            base_url = f'http://{base_url}'

        result = client_types[type].test(
            base_url,
            username,
            password,
            api_token
        )
        return ClientTestResult({
            'success': result[0],
            'description': result[1]
        })

    @staticmethod
    def add(
        type: str,
        title: str,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> BaseTorrentClient:
        """Add a torrent client

        Args:
            type (str): The client identifier.
                A key from `download_torrent_clients.client_types`.

            title (str): The title to give the client

            base_url (str): The base url to use when connecting to the client

            username (Union[str, None]): The username to use when authenticating to the client.
                Allowed to be `None` if not applicable.

            password (Union[str, None]): The password to use when authenticating to the client.
                Allowed to be `None` if not applicable.

            api_token (Union[str, None]): The api token to use when authenticating to the client.
                Allowed to be `None` if not applicable.

        Raises:
            InvalidKeyValue: One of the parameters has an invalid argument
            TorrentClientNotWorking: Testing the client failed.
                The function `download_torrent_clients.TorrentClients.test` returned `False`.

        Returns:
            BaseTorrentClient: An instance of `download_general.TorrentClient`
            representing the newly added client
        """
        if type not in client_types:
            raise InvalidKeyValue('type', type)

        if title is None:
            raise InvalidKeyValue('title', title)

        if base_url is None:
            raise InvalidKeyValue('base_url', base_url)

        if username is not None and password is None:
            raise InvalidKeyValue('password', password)

        base_url = base_url.rstrip('/')
        if not base_url.startswith(('http://', 'https://')):
            base_url = f'http://{base_url}'

        ClientClass = client_types[type]
        test_result = ClientClass.test(
            base_url,
            username,
            password,
            api_token
        )
        if not test_result[0]:
            raise TorrentClientNotWorking(test_result[1])

        data = {
            'type': type,
            'title': title,
            'base_url': base_url,
            'username': username,
            'password': password,
            'api_token': api_token
        }
        data = {
            k: (v if k in (*ClientClass._tokens, 'type') else None)
            for k, v in data.items()
        }

        client_id = get_db().execute("""
            INSERT INTO torrent_clients(
                type, title,
                base_url,
                username, password, api_token
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (data['type'], data['title'],
            data['base_url'],
            data['username'], data['password'], data['api_token'])
        ).lastrowid
        return ClientClass(client_id)

    @staticmethod
    def get_clients() -> List[dict]:
        """Get a list of all torrent clients

        Returns:
            List[dict]: The list with all torrent clients
        """
        cursor = get_db()
        cursor.execute("""
            SELECT
                id, type,
                title, base_url,
                username, password,
                api_token
            FROM torrent_clients
            ORDER BY title, id;
            """
        )
        result = [dict(r) for r in cursor]
        return result

    @staticmethod
    def get_client(id: int) -> BaseTorrentClient:
        """Get a torrent client based on it's ID.

        Args:
            id (int): The ID of the torrent client

        Raises:
            TorrentClientNotFound: The ID does not link to any client

        Returns:
            BaseTorrentClient: An instance of `download_general.BaseTorrentClient`
            representing the client with the given ID.
        """
        client_type = get_db().execute(
            "SELECT type FROM torrent_clients WHERE id = ? LIMIT 1;",
            (id,)
        ).fetchone()

        if not client_type:
            raise TorrentClientNotFound

        return client_types[client_type[0]](id)

# =====================
# Downloading torrents
# =====================


class TorrentDownload(ExternalDownload):
    "For downloading a torrent using a torrent client"

    type = 'torrent'

    def __init__(
        self,
        download_link: str,
        filename_body: str,
        source: DownloadSource,
        custom_name: bool = True
    ) -> None:
        LOGGER.debug(
            f'Creating torrent download: {download_link}, {filename_body}')
        self.id = None # type: ignore
        self.state: DownloadState = DownloadState.QUEUED_STATE
        self.progress: float = 0.0
        self.speed: float = 0.0
        self.size: int = 0
        self.download_link = download_link
        self.source = source

        self.client = None # type: ignore
        self.external_id = None
        self._download_thread = None
        self._download_folder = Settings()['download_folder']

        self._filename_body = filename_body
        self._resulting_files = []
        self._original_file = ''

        self.title = ''
        if custom_name:
            self.title = filename_body.rstrip('.')

        # Find name of torrent as it is folder that it's downloaded in
        try:
            r = Session().post(
                'https://magnet2torrent.com/upload/',
                data={'magnet': download_link}
            )
        except RequestException:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        if r.headers.get('content-type') != 'application/x-bittorrent':
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        name = get_torrent_info(r.content)[b'name'].decode()
        self.title = self._filename_body
        if not custom_name:
            self.title = name
        self.file = join(self._download_folder, name)

        return

    def run(self) -> None:
        self.external_id = self.client.add_download(
            self.download_link,
            self._download_folder,
            self.title
        )
        return

    def update_status(self) -> None:
        if not self.external_id:
            return

        torrent_status = self.client.get_download_status(self.external_id)
        if not torrent_status:
            if torrent_status is None:
                self.state = DownloadState.CANCELED_STATE
            return

        self.progress = torrent_status['progress']
        self.speed = torrent_status['speed']
        self.size = torrent_status['size']
        if self.state not in (
            DownloadState.CANCELED_STATE,
            DownloadState.SHUTDOWN_STATE):
            self.state = torrent_status['state']
        return

    def remove_from_client(self, delete_files: bool) -> None:
        if not self.external_id:
            return

        self.client.delete_download(self.external_id, delete_files)
        return

    def stop(self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        self.state = state
        return

    def todict(self) -> dict:
        return {
            'id': self.id,
            'volume_id': self.volume_id,
            'issue_id': self.issue_id,

            'web_link': self.web_link,
            'web_title': self.web_title,
            'web_sub_title': self.web_sub_title,
            'download_link': self.download_link,
            'pure_link': self.download_link,

            'source': self.source.value,
            'type': self.type,

            'file': self.file,
            'title': self.title,

            'size': self.size,
            'status': self.state.value,
            'progress': self.progress,
            'speed': self.speed,

            'client': self.client.id if self.client else None
        }

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}, {self.download_link}, {self.file}>'
