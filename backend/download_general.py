# -*- coding: utf-8 -*-

"""
General classes (ABC's, base classes) regarding downloading
"""

from abc import ABC, abstractmethod
from threading import Thread
from typing import List, Sequence, Tuple, Union

from backend.custom_exceptions import (ClientDownloading, InvalidKeyValue,
                                       KeyNotFound, TorrentClientNotWorking)
from backend.db import get_db
from backend.enums import DownloadSource, DownloadState


class Download(ABC):
    # This block is assigned after initialisation of the object
    # All types should actually be Union[None, {TYPE}]
    id: int
    volume_id: int
    issue_id: Union[int, None]
    web_link: Union[str, None]
    "Link to webpage for download"
    web_title: Union[str, None]
    "Title of webpage (or release) for download"
    web_sub_title: Union[str, None]
    "Title of sub-section that download falls under (e.g. GC group name)"

    download_link: str
    "The link to the download or service page (e.g. link to MF page)"
    pure_link: str
    "The pure link to download from (e.g. pixeldrain API link or MF folder ID)"
    source: DownloadSource
    type: str

    _filename_body: str
    file: str
    title: str

    size: int
    state: DownloadState
    progress: float
    speed: float

    @abstractmethod
    def __init__(
        self,
        download_link: str,
        filename_body: str,
        source: DownloadSource,
        custom_name: bool = True
    ) -> None:
        """Create the download instance

        Args:
            download_link (str): The link to the download
                (could be direct download link, mega link or magnet link)

            filename_body (str): The body of the file to download to

            source (DownloadSource): The source of the download

            custom_name (bool, optional): Whether or not to use the filename body
            or to use the default name of the download. Defaults to True.

        Raises:
            LinkBroken: The link doesn't work
        """
        return

    @abstractmethod
    def run(self) -> None:
        """Start the download
        """
        return

    @abstractmethod
    def stop(
        self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        """Interrupt the download

        Args:
            state (DownloadState, optional): The state to set for the download.
                Defaults to DownloadState.CANCELED_STATE.
        """
        return

    @abstractmethod
    def todict(self) -> dict:
        """Get a dict representing the download.

        Returns:
            dict: The dict with all information.
        """
        return


class DownloadClient(ABC):
    "A torrent/usenet client"

    id: int
    type: str
    title: str
    base_url: str
    username: Union[str, None]
    password: Union[str, None]
    api_token: Union[str, None]

    _tokens: Sequence[str] = ('title', 'base_url')
    """The keys the client needs or could need for operation
    (mostly whether it's username + password or api_token)"""

    @abstractmethod
    def __init__(self, id: int) -> None:
        """Create a connection with a client.

        Args:
            id (int): The id of the client.
        """
        return

    @abstractmethod
    def todict(self) -> dict:
        """Get info about client in a dict.

        Returns:
            dict: The info about the client.
        """
        return

    @abstractmethod
    def edit(self, edits: dict) -> dict:
        """Edit the client.

        Args:
            edits (dict): The keys and their new values for
            the client settings.

        Raises:
            ClientDownloading: The is a download in the queue using the client.

        Returns:
            dict: The new info of the client.
        """
        return

    @abstractmethod
    def delete(self) -> None:
        """Delete the client.

        Raises:
            ClientDownloading: There is a download in the queue using the client.
        """
        return

    @abstractmethod
    def add_download(self,
        magnet_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        """Add a download to the client.

        Args:
            magnet_link (str): The magnet link of the torrent to download.
            target_folder (str): The folder to download in.
            download_name (Union[str, None]): The name of the download in the client
            Set to `None` to keep original name.

        Returns:
            str: The id/hash of the entry in the download client.
        """
        return

    @abstractmethod
    def get_download_status(self, download_id: str) -> Union[dict, None]:
        """Get the status of the download in a dict

        Args:
            download_id (str): The id/hash of the download to get status of.

        Returns:
            Union[dict, None]: The status of the download,
            empty dict if download is not found
            and `None` if client deleted the download.
        """
        return

    @abstractmethod
    def delete_download(self, download_id: str, delete_files: bool) -> None:
        """Remove the download from the client.

        Args:
            download_id (str): The id/hash of the download to delete.
            delete_files (bool): Delete the downloaded files.
        """
        return

    @staticmethod
    @abstractmethod
    def test(
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> Tuple[bool, Union[str, None]]:
        """Check if a download client is working

        Args:
            base_url (str): The base url on which the client is running.
            username (Union[str, None]): The username to access the client, if set.
            password (Union[str, None]): The password to access the client, if set.
            api_token (Union[str, None]): The api token to access the client, if set.

        Returns:
            Tuple[bool, Union[str, None]]: Whether or not the test succeeded and
            the reason for failing if so.
        """
        return


class ExternalDownload(Download):
    client: DownloadClient
    external_id: Union[str, None]
    _download_thread: Union[Thread, None]
    _download_folder: str
    _resulting_files: List[str]
    _original_file: str

    @abstractmethod
    def update_status(self) -> None:
        """
        Update the various variables about the state/progress
        of the torrent download
        """
        return

    @abstractmethod
    def remove_from_client(self, delete_files: bool) -> None:
        """Remove the download from the client

        Args:
            delete_files (bool): Delete downloaded files
        """
        return


class BaseTorrentClient(DownloadClient):
    def __init__(self, id: int) -> None:
        self.id = id
        data = get_db(dict).execute("""
            SELECT
                type, title,
                base_url,
                username, password,
                api_token
            FROM torrent_clients
            WHERE id = ?
            LIMIT 1;
            """,
            (id,)
        ).fetchone()
        self.type = data['type']
        self.title = data['title']
        self.base_url = data['base_url']
        self.username = data['username']
        self.password = data['password']
        self.api_token = data['api_token']
        return

    def todict(self) -> dict:
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'base_url': self.base_url,
            'username': self.username,
            'password': self.password,
            'api_token': self.api_token
        }

    def edit(self, edits: dict) -> dict:
        cursor = get_db()
        if cursor.execute(
            "SELECT 1 FROM download_queue WHERE torrent_client_id = ? LIMIT 1;",
            (self.id,)
        ).fetchone() is not None:
            raise ClientDownloading(self.id)

        from backend.download_torrent_clients import client_types
        data = {}
        for key in ('title', 'base_url', 'username', 'password', 'api_token'):
            if key in self._tokens and key not in edits:
                raise KeyNotFound(key)
            if key in ('title', 'base_url') and edits[key] is None:
                raise InvalidKeyValue(key, None)
            data[key] = edits.get(key) if key in self._tokens else None

        if data['username'] is not None and data['password'] is None:
            raise InvalidKeyValue('password', data['password'])

        data['base_url'] = data['base_url'].rstrip('/')
        if not data["base_url"].startswith(('http://', 'https://')):
            data["base_url"] = f'http://{data["base_url"]}'

        ClientClass = client_types[self.type]
        test_result = ClientClass.test(
            data['base_url'],
            data['username'],
            data['password'],
            data['api_token']
        )
        if not test_result[0]:
            raise TorrentClientNotWorking(test_result[1])

        cursor.execute("""
            UPDATE torrent_clients SET
                title = ?,
                base_url = ?,
                username = ?,
                password = ?,
                api_token = ?
            WHERE id = ?;
            """,
            (data['title'], data['base_url'],
            data['username'], data['password'], data['api_token'],
            self.id)
        )
        return ClientClass(self.id).todict()

    def delete(self) -> None:
        cursor = get_db()
        if cursor.execute(
            "SELECT 1 FROM download_queue WHERE torrent_client_id = ? LIMIT 1;",
            (self.id,)
        ).fetchone() is not None:
            raise ClientDownloading(self.id)

        cursor.execute(
            "DELETE FROM torrent_clients WHERE id = ?;",
            (self.id,)
        )

        return None

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}; ID {self.id}; {id(self)}>'
