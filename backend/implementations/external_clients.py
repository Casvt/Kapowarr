# -*- coding: utf-8 -*-

from sqlite3 import IntegrityError
from typing import Any, Dict, List, Mapping, Type, Union

from backend.base.custom_exceptions import (ClientDownloading,
                                            ExternalClientNotFound,
                                            ExternalClientNotWorking,
                                            InvalidKeyValue, KeyNotFound)
from backend.base.definitions import (ClientTestResult, DownloadType,
                                      ExternalDownloadClient)
from backend.base.helpers import get_subclasses, normalize_base_url
from backend.internals.db import get_db
from backend.base.logging import LOGGER


# =====================
# region Base External Client
# =====================
class BaseExternalClient(ExternalDownloadClient):
    required_tokens = ('title', 'base_url')

    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def username(self) -> Union[str, None]:
        return self._username

    @property
    def password(self) -> Union[str, None]:
        return self._password

    @property
    def api_token(self) -> Union[str, None]:
        return self._api_token

    def __init__(self, client_id: int) -> None:
        self._id = client_id
        data = get_db().execute("""
            SELECT
                download_type, client_type,
                title, base_url,
                username, password,
                api_token
            FROM external_download_clients
            WHERE id = ?
            LIMIT 1;
            """,
            (client_id,)
        ).fetchone()
        self._title = data['title']
        self._base_url = data['base_url']
        self._username = data['username']
        self._password = data['password']
        self._api_token = data['api_token']
        return

    def get_client_data(self) -> Dict[str, Any]:
        return {
            'id': self._id,
            'download_type': self.download_type.value,
            'client_type': self.client_type,
            'title': self._title,
            'base_url': self._base_url,
            'username': self._username,
            'password': self._password,
            'api_token': self._api_token
        }

    def update_client(self, data: Mapping[str, Any]) -> None:
        cursor = get_db()
        if cursor.execute(
            "SELECT 1 FROM download_queue WHERE external_client_id = ? LIMIT 1;",
            (self.id,)
        ).fetchone() is not None:
            raise ClientDownloading(self.id)

        filtered_data = {}
        for key in ('title', 'base_url', 'username', 'password', 'api_token'):
            if key in self.required_tokens and key not in data:
                raise KeyNotFound(key)

            if key in ('title', 'base_url') and data[key] is None:
                raise InvalidKeyValue(key, None)

            if key == 'base_url':
                filtered_data[key] = normalize_base_url(data[key])

            elif key in self.required_tokens:
                filtered_data[key] = data[key]

            else:
                filtered_data[key] = None

        if (
            filtered_data['username'] is not None # type: ignore
            and filtered_data['password'] is None
        ):
            # Username given but not password
            raise InvalidKeyValue('password', filtered_data['password'])

        fail_reason = self.test(
            filtered_data['base_url'],
            filtered_data['username'],
            filtered_data['password'],
            filtered_data['api_token']
        )
        if fail_reason:
            raise ExternalClientNotWorking(fail_reason)

        cursor.execute("""
            UPDATE external_download_clients
            SET
                title = :title,
                base_url = :base_url,
                username = :username,
                password = :password,
                api_token = :api_token
            WHERE id = :id;
            """,
            {
                **filtered_data,
                "id": self._id
            }
        )
        self._title = filtered_data["title"]
        self._base_url = filtered_data["base_url"]
        self._username = filtered_data["username"]
        self._password = filtered_data["password"]
        self._api_token = filtered_data["api_token"]

        return

    def delete_client(self) -> None:
        try:
            get_db().execute(
                "DELETE FROM external_download_clients WHERE id = ?;",
                (self.id,)
            )

        except IntegrityError:
            raise ClientDownloading(self._id)

        return


# =====================
# region Clients
# =====================
class ExternalClients:
    @staticmethod
    def get_client_types(download_type=None) -> Dict[str, Type[ExternalDownloadClient]]:
        """Get a mapping of the client type strings to their class.

        Args:
            download_type (DownloadType, optional): Filter clients by download type.
                Defaults to None (no filtering).

        Returns:
            Dict[str, Type[ExternalDownloadClient]]: The mapping.
        """
        from backend.implementations.torrent_clients import qBittorrent
        from backend.implementations.usenet_clients.sabnzbd import SABnzbd
    
        clients = get_subclasses(BaseExternalClient)
        
        if download_type is not None:
            clients = [client for client in clients if client.download_type == download_type]
        
        return {
            client.client_type: client
            for client in clients
        }


    @staticmethod
    def test(
        client_type: str,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> ClientTestResult:
        """Test if an external client is supported, working and available.

        Args:
            client_type (str): The client type, which is the value of the
            client's `client_type` attribute.

            base_url (str): The base URL of the client.

            username (Union[str, None]): The username to use when authenticating
            to the client.
                Allowed to be `None` if not applicable.

            password (Union[str, None]): The password to use when authenticating
            to the client.
                Allowed to be `None` if not applicable.

            api_token (Union[str, None]): The api token to use when authenticating
            to the client.
                Allowed to be `None` if not applicable.

        Raises:
            InvalidKeyValue: One of the parameters has an invalid argument.

        Returns:
            ClientTestResult: Whether the test was successful.
        """
        client_types = ExternalClients.get_client_types()
        if client_type not in client_types:
            raise InvalidKeyValue('type', client_type)

        fail_reason = client_types[client_type].test(
            normalize_base_url(base_url),
            username,
            password,
            api_token
        )
        return ClientTestResult({
            'success': fail_reason is None,
            'description': fail_reason
        })

    @staticmethod
    def add(
        client_type: str,
        title: str,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> ExternalDownloadClient:
        """Add an external client.

        Args:
            client_type (str): The client type, which is the value of the
            client's `client_type` attribute.

            title (str): The title to give the client.

            base_url (str): The base URL of the client.

            username (Union[str, None]): The username to use when authenticating
            to the client.
                Allowed to be `None` if not applicable.

            password (Union[str, None]): The password to use when authenticating
            to the client.
                Allowed to be `None` if not applicable.

            api_token (Union[str, None]): The api token to use when authenticating
            to the client.
                Allowed to be `None` if not applicable.

        Raises:
            InvalidKeyValue: One of the parameters has an invalid argument.
            ExternalClientNotWorking: Failed to connect to the client.

        Returns:
            ExternalDownloadClient: The new client.
        """
        if title is None:
            raise InvalidKeyValue('title', title)

        if base_url is None:
            raise InvalidKeyValue('base_url', base_url)

        if username is not None and password is None:
            raise InvalidKeyValue('password', password)

        test_result = ExternalClients.test(
            client_type,
            base_url,
            username,
            password,
            api_token
        )
        if not test_result['success']:
            raise ExternalClientNotWorking(test_result['description'])

        ClientClass = ExternalClients.get_client_types()[client_type]

        data = {
            'download_type': ClientClass.download_type.value,
            'client_type': client_type,
            'title': title,
            'base_url': normalize_base_url(base_url),
            'username': username,
            'password': password,
            'api_token': api_token
        }
        data = {
            k: (
                v
                if k in (
                    *ClientClass.required_tokens,
                    'download_type', 'client_type'
                ) else
                None
            )
            for k, v in data.items()
        }

        client_id = get_db().execute(
            """
            INSERT INTO external_download_clients(
                download_type, client_type,
                title, base_url,
                username, password, api_token
            ) VALUES (
                :download_type, :client_type,
                :title, :base_url,
                :username, :password, :api_token
            );
            """,
            data
        ).lastrowid
        return ExternalClients.get_client(client_id)

    @staticmethod
    def get_clients(download_type=None) -> List[Dict[str, Any]]:
        """Get a list of all external clients.

        Args:
            download_type (DownloadType, optional): Filter clients by download type.
                Defaults to None (no filtering).

        Returns:
            List[Dict[str, Any]]: The list with all external clients.
        """
        cursor = get_db()
        
        if download_type is not None:
            result = cursor.execute("""
                SELECT
                    id, download_type, client_type,
                    title, base_url,
                    username, password,
                    api_token
                FROM external_download_clients
                WHERE download_type = ?
                ORDER BY title, id;
                """,
                (download_type.value,)
            ).fetchalldict()
        else:
            result = cursor.execute("""
                SELECT
                    id, download_type, client_type,
                    title, base_url,
                    username, password,
                    api_token
                FROM external_download_clients
                ORDER BY title, id;
                """
            ).fetchalldict()
        
        return result

    @staticmethod
    def get_client(client_id: int) -> ExternalDownloadClient:
        """Get an external client based on it's ID.

        Args:
            id (int): The ID of the external client.

        Raises:
            ExternalClientNotFound: The ID does not link to any client.

        Returns:
            ExternalDownloadClient: The client.
        """
        client_type = get_db().execute("""
            SELECT client_type
            FROM external_download_clients
            WHERE id = ?
            LIMIT 1;
            """,
            (client_id,)
        ).exists()

        if not client_type:
            raise ExternalClientNotFound

        return ExternalClients.get_client_types()[client_type](client_id)

    @staticmethod
    def get_least_used_client(
        download_type: DownloadType
    ) -> ExternalDownloadClient:
        """Get the least used client of a specific download type.

        Args:
            download_type (DownloadType): The download type to get the client
            for.

        Raises:
            ExternalClientNotFound: No client of the specified type was found.

        Returns:
            ExternalDownloadClient: The least used client.
        """    
        LOGGER.debug(f"Looking for least used client of type: {download_type.value}")
        
        cursor = get_db()
        lu_id = cursor.execute("""
            SELECT clients.id
            FROM download_queue queue
            INNER JOIN external_download_clients clients
                ON queue.external_client_id = clients.id
            WHERE clients.download_type = ?
            GROUP BY clients.id
            ORDER BY COUNT(queue.id)
            LIMIT 1;
            """,
            (download_type.value,)
        ).fetchone()

        if lu_id:
            LOGGER.debug(f"Found least used client with ID: {lu_id[0]}")
            return ExternalClients.get_client(lu_id[0])

        first_id = cursor.execute("""
            SELECT id
            FROM external_download_clients
            WHERE download_type = ?
            LIMIT 1;
            """,
            (download_type.value,)
        ).fetchone()

        if first_id:
            LOGGER.debug(f"No client in use, using first available with ID: {first_id[0]}")
            return ExternalClients.get_client(first_id[0])

        LOGGER.error(f"No client found for download type: {download_type.value}")
        raise ExternalClientNotFound
