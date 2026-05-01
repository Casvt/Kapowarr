# -*- coding: utf-8 -*-

from importlib import import_module
from os.path import basename, dirname, splitext
from typing import Dict, Type, TypeVar

import backend.implementations.download_clients as dc
from backend.base.definitions import Download, DownloadClientIdentifier
from backend.base.files import list_files

DownloadType = TypeVar("DownloadType", bound=Download)


class DownloadClients:
    clients: Dict[DownloadClientIdentifier, Type[Download]] = {}

    @classmethod
    def register_client(cls, identifier: DownloadClientIdentifier):
        """Register a download client for a given service.

        ```
        @DownloadClients.register_client(example_service)
        class ExampleDownload(Download):
            ...
        ```

        Args:
            identifier (DownloadClientIdentifier): The service or protocol that
                the downloader is for.

        Raises:
            RuntimeError: A download client with the given identifier is
                already registered.
        """
        def wrapper(client_class: Type[DownloadType]) -> Type[DownloadType]:
            if identifier in cls.clients:
                raise RuntimeError(
                    f"Download client with identifier {identifier} "
                    "registered multiple times"
                )
            client_class.identifier = identifier
            cls.clients[identifier] = client_class
            return client_class
        return wrapper

    @staticmethod
    def trigger_client_registration() -> None:
        """Import the implementations of the download clients in the
        sub-folders, automatically making them register themselves.
        """
        for file in sorted(
            list_files(
                dirname(dc.__file__ or '')
            ),
            key=lambda f: f.lower()
        ):
            if file.endswith(".py") and not file.endswith("__init__.py"):
                module_name = splitext(basename(file))[0]
                import_module(f"{dc.__name__}.{module_name}")
        return

    @classmethod
    def get_client(cls, identifier: DownloadClientIdentifier) -> Type[Download]:
        """Get a download client based on its identifier.

        Args:
            identifier (DownloadClientIdentifier): The identifier.

        Raises:
            KeyError: Download client with given identifier not found.

        Returns:
            Type[Download]: The download client.
        """
        return cls.clients[identifier]
