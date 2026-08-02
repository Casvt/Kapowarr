# -*- coding: utf-8 -*-

from importlib import import_module
from os.path import basename, dirname, splitext
from typing import Dict, Type, TypeVar

import backend.implementations.download_preppers as dp
from backend.base.definitions import DownloadPrepper, DownloadType
from backend.base.files import list_files

DownloadPrepperType = TypeVar(
    "DownloadPrepperType",
    bound=DownloadPrepper
)


class DownloadPreppers:
    preppers: Dict[DownloadType, Dict[str, Type[DownloadPrepper]]] = {
        dt: {}
        for dt in DownloadType
    }

    @classmethod
    def register_prepper(cls, download_type: DownloadType, client_type: str):
        """Register a download prepper.

        ```
        @DownloadPreppers.register_client(
            DownloadType.TORRENT, "ProductName"
        )
        class ExamplePrepper(DownloadPrepper):
            ...
        ```

        Args:
            download_type (DownloadType): The protocol that the client preps
                downloads for.
            client_type (str): The name of the indexer client (e.g. 'Torznab').

        Raises:
            RuntimeError: A download prepper with the given client type is
                already registered for the download type.
        """
        def wrapper(
            client_class: Type[DownloadPrepperType]
        ) -> Type[DownloadPrepperType]:
            if client_type in cls.preppers[download_type]:
                raise RuntimeError(
                    f"Indexer client with client type {client_type} "
                    f"(download type {download_type.name}) "
                    "registered multiple times"
                )
            cls.preppers[download_type][client_type] = client_class
            client_class.download_type = download_type
            client_class.client_type = client_type
            return client_class
        return wrapper

    @staticmethod
    def trigger_prepper_registration() -> None:
        """
        Import the implementations of the download preppers in the
        sub-folders, automatically making them register themselves.
        """
        for file in sorted(
            list_files(
                dirname(dp.__file__ or ''),
                (".py",)
            ),
            key=lambda f: f.lower()
        ):
            if file.endswith("__init__.py"):
                continue

            foldername = basename(dirname(file))
            filename = splitext(basename(file))[0]
            module_path = f"{dp.__name__}.{foldername}.{filename}"
            import_module(module_path)
        return

    @classmethod
    def get_prepper(
        cls,
        download_type: DownloadType,
        client_type: str
    ) -> Type[DownloadPrepper]:
        """Get a download prepper based on its download type and client type.

        Args:
            download_type (DownloadType): The protocol that the client preps
                downloads for.
            client_type (str): The name of the indexer client (e.g. 'Torznab').

        Raises:
            KeyError: Download prepper with given download type and client type
                not found.

        Returns:
            Type[DownloadPrepper]: The download prepper.
        """
        return cls.preppers[download_type][client_type]
