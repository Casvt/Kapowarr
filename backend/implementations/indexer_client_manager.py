# -*- coding: utf-8 -*-

"""
The manager of indexer clients and their base class
"""

from importlib import import_module
from os.path import basename, dirname, splitext
from typing import Any, Dict, List, Mapping, Tuple, Type, TypeVar, Union

import backend.implementations.indexer_clients as ic
from backend.base.custom_exceptions import (AddingIndexerForbidden,
                                            ClientNotWorking,
                                            CredentialInvalid, IndexerNotFound,
                                            InvalidKeyValue, KeyNotFound)
from backend.base.definitions import (ClientTestResult, DownloadType,
                                      GCDownloadService, IndexerClient,
                                      IndexerClientData, IndexerClientField)
from backend.base.files import list_files
from backend.base.helpers import CommaList, normalise_base_url
from backend.base.logging import LOGGER
from backend.internals.db import get_db

ICF = IndexerClientField


def _validate_indexer_data(
    data: Mapping[str, Any],
    required_tokens: Tuple[IndexerClientField, ...]
) -> Dict[str, Any]:
    filtered_data: Dict[str, Any] = {}
    for key in ICF._member_map_.values():
        if key not in required_tokens:
            continue

        if key.value not in data:
            raise KeyNotFound(key.value)

        value = data[key.value]

        if (
            key in (
                ICF.TITLE,
                ICF.ENABLED,
                ICF.URL
            )
            and value is None
        ):
            raise InvalidKeyValue(key.value, None)

        if key == ICF.URL:
            if not isinstance(value, str):
                raise InvalidKeyValue(key.value, value)
            filtered_data[key.value] = normalise_base_url(value)

        elif key == ICF.ENABLED:
            if not isinstance(value, bool):
                raise InvalidKeyValue(key.value, value)
            filtered_data[key.value] = value

        elif (
            key == ICF.GC_SERVICE_PREFERENCE
            and value is not None
        ):
            if not isinstance(value, list):
                raise InvalidKeyValue(key.value, value)

            value = CommaList(value)

            available = [
                s.value
                for s in GCDownloadService._member_map_.values()
            ]

            for entry in value:
                if entry not in available:
                    raise InvalidKeyValue(key.value, value)

            for entry in available:
                if entry not in value:
                    raise InvalidKeyValue(key.value, value)

            filtered_data[key.value] = str(value)

        elif (
            key == ICF.GC_AVOID_LARGE_DOWNLOADS
            and value is not None
        ):
            if not isinstance(value, bool):
                raise InvalidKeyValue(key.value, value)
            filtered_data[key.value] = value

        elif key in required_tokens:
            if not isinstance(value, str):
                raise InvalidKeyValue(key.value, value)
            filtered_data[key.value] = value

        else:
            filtered_data[key.value] = None

    return filtered_data


# region Base Indexer Client
class BaseIndexerClient(IndexerClient):
    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    def __init__(self, indexer_id: int) -> None:
        self._id = indexer_id
        data = get_db().execute("""
            SELECT
                enabled,
                title, url,
                gc_service_preference, gc_avoid_large_downloads
            FROM indexer_clients
            WHERE id = ?
            LIMIT 1;
            """,
            (indexer_id,)
        ).fetchone()
        self._enabled: bool = data['enabled']
        self._title: str = data['title']
        self._url: str = data['url']

        if (
            data["gc_service_preference"] is not None
            and data["gc_avoid_large_downloads"] is not None
        ):
            self._gc_service_preference = CommaList(
                data["gc_service_preference"])
            self._gc_avoid_large_downloads = data["gc_avoid_large_downloads"]
        else:
            self._gc_service_preference = None
            self._gc_avoid_large_downloads = None

        return

    def get_indexer_data(self) -> IndexerClientData:
        return {
            'id': self._id,
            'enabled': self._enabled,
            'download_type': self.download_type.value,
            'client_type': self.client_type,
            'required_tokens': [rt.value for rt in self.required_tokens],
            'title': self._title,
            'url': self._url,
            'gc_service_preference': self._gc_service_preference,
            'gc_avoid_large_downloads': self._gc_avoid_large_downloads
        }

    def update_indexer(self, data: Mapping[str, Any]) -> None:
        LOGGER.info(f"Updating indexer {self._id}: {data}")
        filtered_data = _validate_indexer_data(data, self.required_tokens)

        # Raises exception on fail
        self.test(filtered_data[ICF.URL.value])

        get_db().execute("""
            UPDATE indexer_clients
            SET
                enabled = :enabled,
                title = :title,
                url = :url,
                gc_service_preference = :gc_service_preference,
                gc_avoid_large_downloads = :gc_avoid_large_downloads
            WHERE id = :id;
            """,
            {
                **filtered_data,
                "id": self._id
            }
        )
        self._enabled = filtered_data[ICF.ENABLED.value]
        self._title = filtered_data[ICF.TITLE.value]
        self._url = filtered_data[ICF.URL.value]
        if (
            "gc_service_preference" in self.required_tokens
            and "gc_avoid_large_downloads" in self.required_tokens
        ):
            self._gc_service_preference = CommaList(
                filtered_data["gc_service_preference"]
            )
            self._gc_avoid_large_downloads = filtered_data[
                "gc_avoid_large_downloads"
            ]

        return

    def delete_indexer(self) -> None:
        LOGGER.info(f'Deleting indexer {self.id}')
        get_db().execute(
            "DELETE FROM indexer_clients WHERE id = ?;",
            (self.id,)
        )
        return


# region Clients
IndexerClientType = TypeVar(
    "IndexerClientType",
    bound=IndexerClient
)


class IndexerClients:
    clients: Dict[DownloadType, Dict[str, Type[IndexerClient]]] = {
        dt: {}
        for dt in DownloadType
    }

    @classmethod
    def register_client(
        cls,
        download_type: DownloadType,
        client_type: str,
        required_tokens: Tuple[IndexerClientField, ...],
        allow_multiple_instances: bool
    ):
        """Register an indexer client.

        ```
        @IndexerClients.register_client(
            DownloadType.TORRENT, 'ProductName',
            (ICF.TITLE, ICF.ENABLED, ICF.URL),
            allow_multiple_instances=True
        )
        class ProductName(IndexerClient):
            ...
        ```

        Args:
            download_type (DownloadType): The protocol that the client supplies
                downloads for.
            client_type (str): The name of the indexer client (e.g. 'Torznab').
            required_tokens (Tuple[IndexerClientField, ...]): The fields that
                the client needs.
            allow_multiple_instances (bool): Allow this client to be added
                multiple times. For something like Torznab, you want that. For
                something like GC, you don't want to allow that.

        Raises:
            RuntimeError: An indexer client with the given client type is
                already registered for the download type.
        """
        def wrapper(
            client_class: Type[IndexerClientType]
        ) -> Type[IndexerClientType]:
            if client_type in cls.clients[download_type]:
                raise RuntimeError(
                    f"Indexer client with client type {client_type} "
                    f"(download type {download_type.name}) "
                    "registered multiple times"
                )
            cls.clients[download_type][client_type] = client_class
            client_class.download_type = download_type
            client_class.client_type = client_type
            client_class.required_tokens = required_tokens
            client_class.allow_multiple_instances = allow_multiple_instances
            return client_class
        return wrapper

    @staticmethod
    def trigger_client_registration() -> None:
        """
        Import the implementations of the indexer clients in the sub-folders,
        automatically making them register themselves.
        """
        for file in sorted(
            list_files(
                dirname(ic.__file__ or ''),
                (".py",)
            ),
            key=lambda f: f.lower()
        ):
            if file.endswith("__init__.py"):
                continue

            foldername = basename(dirname(file))
            filename = splitext(basename(file))[0]
            module_path = f"{ic.__name__}.{foldername}.{filename}"
            import_module(module_path)
        return

    @classmethod
    def test(
        cls,
        download_type: DownloadType,
        client_type: str,
        url: str
    ) -> ClientTestResult:
        """Test whether an indexer client is supported, working and available.

        Args:
            download_type (DownloadType): The protocol that the client supplies
                downloads for.

            client_type (str): The client type of the client, as supplied when
                they registered to this class.

            url (str): The url on which the indexer is available.

        Raises:
            InvalidKeyValue: One of the parameters has an invalid argument.

        Returns:
            ClientTestResult: Whether the test was successful.
        """
        try:
            type_clients = cls.clients[download_type]
        except KeyError:
            raise InvalidKeyValue('download_type', download_type)

        try:
            type_clients[client_type].test(normalise_base_url(url))

        except KeyError:
            raise InvalidKeyValue('client_type', client_type)

        except ClientNotWorking as e:
            return ClientTestResult({
                'success': False,
                'description': e.reason.value
            })

        except CredentialInvalid:
            return ClientTestResult({
                'success': False,
                'description': 'invalid_credentials'
            })

        else:
            return ClientTestResult({
                'success': True,
                'description': None
            })

    @classmethod
    def add(
        cls,
        download_type: DownloadType,
        client_type: str,
        enabled: bool,
        title: str,
        url: str,
        gc_service_preference: Union[CommaList, None],
        gc_avoid_large_downloads: Union[bool, None]
    ) -> IndexerClient:
        """Add an indexer client.

        Args:
            download_type (DownloadType): The protocol that the client supplies
                downloads for.

            client_type (str): The client type of the client, as supplied when
                they registered to this class.

            enabled (bool): Whether the indexer is enabled or not.

            title (str): The title to give the indexer.

            url (str): The url on which the indexer is available.

            gc_service_preference (Union[CommaList, None]): Only applicable for
                the GC client. The preference order for download services
                offered on a GC download page.

            gc_avoid_large_downloads (Union[bool, None]): Only applicable for
                the GC client. Whether to avoid downloads if they're over 400MB.

        Raises:
            InvalidKeyValue: One of the parameters has an invalid argument.
            AddingIndexerForbidden: Not allowed to add another instance of this
                indexer client.
            ClientNotWorking: Can't connect to client.
            CredentialInvalid: Credentials are invalid.

        Returns:
            IndexerClient: The new client.
        """
        try:
            type_clients = cls.clients[download_type]
        except KeyError:
            raise InvalidKeyValue('download_type', download_type)

        try:
            ClientClass = type_clients[client_type]
        except KeyError:
            raise InvalidKeyValue('client_type', client_type)

        cursor = get_db()
        if not ClientClass.allow_multiple_instances:
            cursor.execute("""
                SELECT 1
                FROM indexer_clients
                WHERE download_type = ?
                    AND client_type = ?
                LIMIT 1;
                """,
                (download_type, client_type)
            )
            if cursor.exists():
                raise AddingIndexerForbidden(download_type, client_type)

        data = {
            'enabled': enabled,
            'title': title,
            'url': url,
            'gc_service_preference': gc_service_preference,
            'gc_avoid_large_downloads': gc_avoid_large_downloads
        }
        LOGGER.info(
            f"Adding indexer: {download_type=}, {client_type=}, {data=}"
        )
        filtered_data = _validate_indexer_data(
            data,
            ClientClass.required_tokens
        )

        # Raises exception on fail
        ClientClass.test(filtered_data["url"])

        filtered_data.update({
            'download_type': ClientClass.download_type.value,
            'client_type': client_type
        })

        indexer_id = cursor.execute(
            """
            INSERT INTO indexer_clients(
                enabled,
                download_type, client_type,
                title, url,
                gc_service_preference, gc_avoid_large_downloads
            ) VALUES (
                :enabled,
                :download_type, :client_type,
                :title, :url,
                :gc_service_preference, :gc_avoid_large_downloads
            );
            """,
            filtered_data
        ).lastrowid
        return cls.get_client(indexer_id)

    @classmethod
    def get_all_data(cls) -> List[IndexerClientData]:
        """Get a list of all data of the indexer clients.

        Returns:
            List[IndexerClientData]: The list of all data of the indexer clients.
        """
        cursor = get_db()
        cursor.execute("""
            SELECT
                id, enabled,
                download_type, client_type,
                title, url,
                gc_service_preference, gc_avoid_large_downloads
            FROM indexer_clients
            ORDER BY title, id;
        """)

        result: List[IndexerClientData] = []
        for client in cursor:
            ClientClass = (cls
                .clients[DownloadType(client["download_type"])]
                [client["client_type"]]
            )
            if client["gc_service_preference"] is not None:
                gc_service_preference = CommaList(
                    client["gc_service_preference"])
            else:
                gc_service_preference = None

            result.append({
                "id": client["id"],
                "enabled": client["enabled"],
                "download_type": client["download_type"],
                "client_type": client["client_type"],
                "required_tokens": [
                    t.value
                    for t in ClientClass.required_tokens
                ],
                "title": client["title"],
                "url": client["url"],
                "gc_service_preference": gc_service_preference,
                "gc_avoid_large_downloads": client["gc_avoid_large_downloads"]
            })

        return result

    @classmethod
    def get_all_clients(cls) -> List[IndexerClient]:
        """Get a list of all indexer clients.

        Returns:
            List[IndexerClient]: The list of all indexer clients.
        """
        cursor = get_db()
        cursor.execute("""
            SELECT download_type, client_type, id
            FROM indexer_clients
            ORDER BY title, id;
        """)

        return [
            cls.clients[DownloadType(client[0])][client[1]](client[2])
            for client in cursor
        ]

    @classmethod
    def get_client(cls, indexer_id: int) -> IndexerClient:
        """Get an indexer client based on its ID.

        Args:
            indexer_id (int): The ID of the indexer client.

        Raises:
            IndexerNotFound: The ID does not link to any client.

        Returns:
            IndexerClient: The client.
        """
        client = get_db().execute("""
            SELECT download_type, client_type
            FROM indexer_clients
            WHERE id = ?
            LIMIT 1;
            """,
            (indexer_id,)
        ).fetchone()

        if not client:
            raise IndexerNotFound(indexer_id)

        return cls.clients[DownloadType(client[0])][client[1]](indexer_id)
