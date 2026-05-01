# -*- coding: utf-8 -*-

"""
The manager of external download clients and their base class
"""

from importlib import import_module
from os.path import basename, dirname, splitext
from re import IGNORECASE, compile
from sqlite3 import IntegrityError
from typing import Any, Dict, List, Mapping, Tuple, Type, TypeVar, Union, cast

import backend.implementations.external_clients as ec
from backend.base.custom_exceptions import (ClientNotWorking,
                                            CredentialInvalid,
                                            ExternalClientDownloading,
                                            ExternalClientNotFound,
                                            InvalidKeyValue, KeyNotFound)
from backend.base.definitions import (ClientTestResult, DownloadType,
                                      ExternalClientField,
                                      ExternalDownloadClient,
                                      ExternalDownloadClientData)
from backend.base.files import list_files
from backend.base.helpers import normalise_base_url
from backend.base.logging import LOGGER
from backend.internals.db import get_db

ECF = ExternalClientField
filename_magnet_link = compile(r'(?<=&dn=).*?(?=&)', IGNORECASE)


# region Base External Client
class BaseExternalClient(ExternalDownloadClient):
    @property
    def id(self) -> int:
        return self._id

    @property
    def enabled(self) -> bool:
        return self._enabled

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
                enabled,
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
        self._enabled = data['enabled']
        self._title = data['title']
        self._base_url = data['base_url']
        self._username = data['username']
        self._password = data['password']
        self._api_token = data['api_token']
        return

    def get_client_data(self) -> ExternalDownloadClientData:
        return {
            'id': self._id,
            'enabled': self._enabled,
            'download_type': self.download_type.value,
            'client_type': self.client_type,
            'required_tokens': [rt.value for rt in self.required_tokens],
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
            raise ExternalClientDownloading(self.id)

        filtered_data: Dict[str, Any] = {}
        for key in ECF._member_map_.values():
            if key in self.required_tokens and key.value not in data:
                raise KeyNotFound(key.value)

            if (
                key in (ECF.TITLE, ECF.ENABLED, ECF.BASE_URL)
                and data[key.value] is None
            ):
                raise InvalidKeyValue(key.value, None)

            if key == ECF.BASE_URL:
                if not isinstance(data[key.value], str):
                    raise InvalidKeyValue(key.value, data[key.value])
                filtered_data[key.value] = normalise_base_url(data[key.value])

            elif key == ECF.ENABLED:
                if not isinstance(data[key.value], bool):
                    raise InvalidKeyValue(key.value, data[key.value])
                filtered_data[key.value] = data[key.value]

            elif key in self.required_tokens:
                if not isinstance(data[key.value], str):
                    raise InvalidKeyValue(key.value, data[key.value])
                filtered_data[key.value] = data[key.value]

            else:
                filtered_data[key.value] = None

        if (
            filtered_data[ECF.USERNAME.value] is not None
            and filtered_data[ECF.PASSWORD.value] is None
        ):
            # Username given but not password
            raise InvalidKeyValue(
                ECF.PASSWORD.value,
                filtered_data[ECF.PASSWORD.value]
            )

        # Raises exception on fail
        self.test(
            filtered_data[ECF.BASE_URL.value],
            filtered_data[ECF.USERNAME.value],
            filtered_data[ECF.PASSWORD.value],
            filtered_data[ECF.API_TOKEN.value]
        )

        cursor.execute("""
            UPDATE external_download_clients
            SET
                enabled = :enabled,
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
        self._enabled = filtered_data[ECF.ENABLED.value]
        self._title = filtered_data[ECF.TITLE.value]
        self._base_url = filtered_data[ECF.BASE_URL.value]
        self._username = filtered_data[ECF.USERNAME.value]
        self._password = filtered_data[ECF.PASSWORD.value]
        self._api_token = filtered_data[ECF.API_TOKEN.value]

        return

    def delete_client(self) -> None:
        try:
            get_db().execute(
                "DELETE FROM external_download_clients WHERE id = ?;",
                (self.id,)
            )

        except IntegrityError:
            raise ExternalClientDownloading(self._id)

        return


# region Clients
ExternalDownloadClientType = TypeVar(
    "ExternalDownloadClientType",
    bound=ExternalDownloadClient
)


class ExternalClients:
    clients: Dict[DownloadType, Dict[str, Type[ExternalDownloadClient]]] = {
        dt: {}
        for dt in DownloadType
    }
    instances: Dict[int, ExternalDownloadClient] = {}

    @classmethod
    def register_client(
        cls,
        download_type: DownloadType,
        client_type: str,
        required_tokens: Tuple[ExternalClientField, ...]
    ):
        """Register an external download client.

        ```
        @ExternalClients.register_client(
            DownloadType.TORRENT, 'ProductName',
            (ECF.TITLE, ECF.BASE_URL, ECF.USERNAME, ECF.PASSWORD)
        )
        class ProductName(ExternalDownloadClient):
            ...
        ```

        Args:
            download_type (DownloadType): The protocol that the client handles.
            client_type (str): The product name of the client (e.g. 'qBittorrent').
            required_tokens (Tuple[ExternalClientField, ...]): The fields that
                the client needs.

        Raises:
            RuntimeError: An external client with the given client type is
                already registered for the download type.
        """
        def wrapper(
            client_class: Type[ExternalDownloadClientType]
        ) -> Type[ExternalDownloadClientType]:
            if client_type in cls.clients[download_type]:
                raise RuntimeError(
                    f"External client with client type {client_type} "
                    f"(download type {download_type.name}) "
                    "registered multiple times"
                )
            cls.clients[download_type][client_type] = client_class
            client_class.download_type = download_type
            client_class.client_type = client_type
            client_class.required_tokens = required_tokens
            return client_class
        return wrapper

    @staticmethod
    def trigger_client_registration() -> None:
        """Import the implementations of the external download clients in the
        sub-folders, automatically making them register themselves.
        """
        for file in sorted(
            list_files(
                dirname(ec.__file__ or ''),
                (".py",)
            ),
            key=lambda f: f.lower()
        ):
            if file.endswith("__init__.py"):
                continue

            foldername = basename(dirname(file))
            filename = splitext(basename(file))[0]
            module_path = f"{ec.__name__}.{foldername}.{filename}"
            import_module(module_path)
        return

    @classmethod
    def disconnect_clients(cls) -> None:
        """Run the shutdown handler of all connected clients.
        """
        LOGGER.debug("Disconnecting external clients")
        for client in cls.instances.values():
            try:
                client.on_shutdown()
            except ClientNotWorking:
                # It's okay if we can't communicate,
                # as we're shutting down anyway
                pass
        return

    @classmethod
    def test(
        cls,
        download_type: DownloadType,
        client_type: str,
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> ClientTestResult:
        """Test whether an external client is supported, working and available.

        Args:
            download_type (DownloadType): The protocol that the client handles.

            client_type (str): The client type of the client, as supplied when
                they registered to this class.

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
        try:
            type_clients = cls.clients[download_type]
        except KeyError:
            raise InvalidKeyValue('download_type', download_type)

        try:
            type_clients[client_type].test(
                normalise_base_url(base_url),
                username,
                password,
                api_token
            )

        except KeyError:
            raise InvalidKeyValue('client_type', client_type)

        except ClientNotWorking as e:
            return ClientTestResult({
                'success': False,
                'description': e.reason_text
            })

        except CredentialInvalid:
            return ClientTestResult({
                'success': False,
                'description': 'Failed to login with the given credentials'
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
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> ExternalDownloadClient:
        """Add an external client.

        Args:
            download_type (DownloadType): The protocol that the client handles.

            client_type (str): The client type of the client, as supplied when
                they registered to this class.

            enabled (bool): Whether the client is enabled or not.

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
            ClientNotWorking: Can't connect to client.
            CredentialInvalid: Credentials are invalid.

        Returns:
            ExternalDownloadClient: The new client.
        """
        if not isinstance(enabled, bool):
            raise InvalidKeyValue('enabled', enabled)

        if title is None:
            raise InvalidKeyValue('title', title)

        if base_url is None:
            raise InvalidKeyValue('base_url', base_url)

        if username is not None and password is None:
            raise InvalidKeyValue('password', password)

        try:
            type_clients = cls.clients[download_type]
        except KeyError:
            raise InvalidKeyValue('download_type', download_type)

        try:
            ClientClass = type_clients[client_type]
        except KeyError:
            raise InvalidKeyValue('client_type', client_type)

        ClientClass.test(
            normalise_base_url(base_url),
            username,
            password,
            api_token
        )

        allowed_keys = [
            rt.value
            for rt in ClientClass.required_tokens
        ]
        data = {
            'enabled': enabled,
            'title': title,
            'base_url': normalise_base_url(base_url),
            'username': username,
            'password': password,
            'api_token': api_token
        }
        data = {
            k: v if k in allowed_keys else None
            for k, v in data.items()
        }
        data.update({
            'download_type': ClientClass.download_type.value,
            'client_type': client_type
        })

        client_id = get_db().execute(
            """
            INSERT INTO external_download_clients(
                enabled,
                download_type, client_type,
                title, base_url,
                username, password, api_token
            ) VALUES (
                :enabled,
                :download_type, :client_type,
                :title, :base_url,
                :username, :password, :api_token
            );
            """,
            data
        ).lastrowid
        return cls.get_client(client_id)

    @classmethod
    def get_clients(cls) -> List[ExternalDownloadClientData]:
        """Get a list of all external clients.

        Returns:
            List[ExternalDownloadClientData]: The list with all external clients.
        """
        result = cast(List[ExternalDownloadClientData], [
            {
                **client,
                "required_tokens": [
                    rt.value
                    for rt in cls.clients
                    [DownloadType(client["download_type"])]
                    [client["client_type"]]
                    .required_tokens
                ]
            }
            for client in get_db().execute("""
                SELECT
                    id, enabled,
                    download_type, client_type,
                    title, base_url,
                    username, password,
                    api_token
                FROM external_download_clients
                ORDER BY title, id;
                """
            ).fetchalldict()
        ])
        return result

    @classmethod
    def get_client(cls, client_id: int) -> ExternalDownloadClient:
        """Get an external client based on its ID.

        Args:
            client_id (int): The ID of the external client.

        Raises:
            ExternalClientNotFound: The ID does not link to any client.

        Returns:
            ExternalDownloadClient: The client.
        """
        if client_id in cls.instances:
            return cls.instances[client_id]

        client_types = get_db().execute("""
            SELECT download_type, client_type
            FROM external_download_clients
            WHERE id = ?
            LIMIT 1;
            """,
            (client_id,)
        ).fetchone()

        if not client_types:
            raise ExternalClientNotFound(client_id)

        cls.instances[client_id] = (cls
            .clients
            [DownloadType(client_types[0])]
            [client_types[1]]
            (client_id)
        )
        return cls.instances[client_id]

    @classmethod
    def get_least_used_client(
        cls,
        download_type: DownloadType
    ) -> ExternalDownloadClient:
        """Get the least used client of a specific download type that is enabled.

        Args:
            download_type (DownloadType): The download type to get the client
                for.

        Raises:
            ExternalClientNotFound: No client of the specified type was found
                or all of them are disabled.

        Returns:
            ExternalDownloadClient: The least used client.
        """
        least_used_id = get_db().execute("""
            SELECT clients.id
            FROM external_download_clients clients
            LEFT JOIN download_queue queue
            ON clients.id = queue.external_client_id
            WHERE clients.download_type = ?
                AND clients.enabled = 1
            GROUP BY clients.id
            ORDER BY COUNT(queue.id)
            LIMIT 1;
            """,
            (download_type.value,)
        ).exists()

        if least_used_id:
            return cls.get_client(least_used_id)

        raise ExternalClientNotFound(-1)

    @classmethod
    def delete_client(cls, client_id: int) -> None:
        """Delete a client.

        Args:
            client_id (int): The ID of the client.

        Raises:
            ExternalClientNotFound: The ID does not link to any client.
            ExternalClientDownloading: There is a download using the client.
        """
        cls.get_client(client_id).delete_client()

        if client_id in cls.instances:
            cls.instances[client_id].on_shutdown()
            del cls.instances[client_id]

        return
