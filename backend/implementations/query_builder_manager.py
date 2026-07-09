# -*- coding: utf-8 -*-

from importlib import import_module
from os.path import basename, dirname, splitext
from typing import Dict, Type, TypeVar

import backend.implementations.query_builders as qb
from backend.base.definitions import DownloadType, QueryBuilder
from backend.base.files import list_files

QueryBuilderType = TypeVar("QueryBuilderType", bound=QueryBuilder)


class QueryBuilders:
    builders: Dict[DownloadType, Type[QueryBuilder]] = {}

    @classmethod
    def register_builder(cls, download_type: DownloadType):
        """Register a query builder for a given download type.

        ```
        @QueryBuilders.register_builder(DownloadType.TORRENT)
        class TorrentQueryBuilder(QueryBuilder):
            ...
        ```

        Args:
            download_type (DownloadType): The service or protocol that
                the builder is for.

        Raises:
            RuntimeError: A builder for the given download type is
                already registered.
        """
        def wrapper(
            builder_class: Type[QueryBuilderType]
        ) -> Type[QueryBuilderType]:
            if download_type in cls.builders:
                raise RuntimeError(
                    f"Query builder for {download_type=} "
                    "registered multiple times"
                )
            builder_class.download_type = download_type
            cls.builders[download_type] = builder_class
            return builder_class
        return wrapper

    @staticmethod
    def trigger_builder_registration() -> None:
        """Import the implementations of the query builders in the
        sub-folders, automatically making them register themselves.
        """
        for file in sorted(
            list_files(
                dirname(qb.__file__ or '')
            ),
            key=lambda f: f.lower()
        ):
            if file.endswith(".py") and not file.endswith("__init__.py"):
                module_name = splitext(basename(file))[0]
                import_module(f"{qb.__name__}.{module_name}")
        return

    @classmethod
    def get_builder(cls, download_type: DownloadType) -> Type[QueryBuilder]:
        """Get a query builder based on the download type.

        Args:
            download_type (DownloadType): The download type.

        Raises:
            KeyError: Query builder for the given download type not found.

        Returns:
            Type[QueryBuilder]: The query builder.
        """
        return cls.builders[download_type]
