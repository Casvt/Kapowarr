# -*- coding: utf-8 -*-

from os.path import abspath, isdir
from sqlite3 import IntegrityError
from typing import List, Union, cast

from backend.base.custom_exceptions import (ExternalClientNotFound,
                                            FolderNotFound,
                                            RemoteMappingInvalid,
                                            RemoteMappingNotFound)
from backend.base.definitions import RemoteMappingData
from backend.base.files import folder_is_inside_folder, uppercase_drive_letter
from backend.base.helpers import force_suffix
from backend.base.logging import LOGGER
from backend.internals.db import get_db


def _local_folder_is_valid(
    external_download_client_id: int,
    local_path: str,
    skip_mapping_id: Union[int, None] = None
) -> bool:
    """Check whether a local path is not a child or parent of other local paths.

    Args:
        external_download_client_id (int): The ID of the external download client
            that the local_path is for.

        local_path (str): The path to check.

        skip_mapping_id (Union[int, None], optional): When given an ID of a
            mapping, skip that mapping in the check. Useful in case you don't
            want to check against the old value of the mapping itself.
            Defaults to None.

    Returns:
        bool: Whether it's valid.
    """
    for entry in RemoteMappings.get_all():
        if external_download_client_id != entry['external_download_client_id']:
            continue

        if local_path == entry['local_path']:
            continue

        if entry['id'] == (skip_mapping_id or -1):
            continue

        if (
            folder_is_inside_folder(
                local_path, entry['local_path']
            )
            or folder_is_inside_folder(
                entry['local_path'], local_path
            )
        ):
            return False

    return True


def _remote_folder_is_valid(
    external_download_client_id: int,
    remote_path: str,
    skip_mapping_id: Union[int, None] = None
) -> bool:
    """Check whether a remote path is not a child or parent of other remote paths.

    Args:
        external_download_client_id (int): The ID of the external download client
            that the remote_path is for.

        remote_path (str): The path to check.

        skip_mapping_id (Union[int, None], optional): When given an ID of a
            mapping, skip that mapping in the check. Useful in case you don't
            want to check against the old value of the mapping itself.
            Defaults to None.

    Returns:
        bool: Whether it's valid.
    """
    for entry in RemoteMappings.get_all():
        if external_download_client_id != entry['external_download_client_id']:
            continue

        if remote_path == entry['remote_path']:
            continue

        if entry['id'] == (skip_mapping_id or -1):
            continue

        if (
            folder_is_inside_folder(
                remote_path, entry['remote_path']
            )
            or folder_is_inside_folder(
                entry['remote_path'], remote_path
            )
        ):
            return False

    return True


class RemoteMapping:
    def __init__(self, mapping_id: int) -> None:
        """Create an instance.

        Args:
            mapping_id (int): The ID of the mapping.

        Raises:
            RemoteMappingNotFound: Mapping with given ID does not exist.
        """
        self.id = mapping_id

        data = get_db().execute("""
            SELECT 1
            FROM remote_mappings
            WHERE id = ?
            LIMIT 1;
            """,
            (self.id,)
        ).fetchonedict()

        if not data:
            raise RemoteMappingNotFound(mapping_id)

        return

    def get(self) -> RemoteMappingData:
        """Get the data of the mapping.

        Returns:
            RemoteMappingData: The data.
        """
        return cast(RemoteMappingData, get_db().execute("""
            SELECT id, external_download_client_id, remote_path, local_path
            FROM remote_mappings
            WHERE id = ?
            LIMIT 1;
            """,
            (self.id,)
        ).fetchonedict())

    def update(
        self,
        external_download_client_id: Union[int, None] = None,
        remote_path: Union[str, None] = None,
        local_path: Union[str, None] = None
    ) -> RemoteMappingData:
        """Edit the mapping.

        Args:
            external_download_client_id (Union[int, None], optional): The ID of
                the new external download client that the mapping is for.
                Defaults to None.

            remote_path (Union[str, None], optional): The new remote path.
                Defaults to None.

            local_path (Union[str, None], optional): The new local path.
                Defaults to None.

        Raises:
            FolderNotFound: The local path could not be found.
            ExternalClientNotFound: The external download client could not be
                found based on the given ID.
            RemoteMappingInvalid: The local path or remote path is a child or
                parent of another local/remote path for the client.

        Returns:
            RemoteMappingData: The new data.
        """
        LOGGER.info(
            f'Updating remote mapping {self.id}: {external_download_client_id=}, '
            f'{remote_path=}, {local_path=}')

        data = self.get()
        new_values = {
            'external_download_client_id': external_download_client_id,
            'remote_path': remote_path,
            'local_path': local_path
        }

        for k, v in new_values.items():
            if v is not None:
                data[k] = v

        if local_path:
            formatted_local_path = uppercase_drive_letter(
                force_suffix(abspath(local_path))
            )

            if not isdir(formatted_local_path):
                raise FolderNotFound(local_path)

            if not _local_folder_is_valid(
                data['external_download_client_id'],
                formatted_local_path, data['id']
            ):
                raise RemoteMappingInvalid(local_path)

            data['local_path'] = formatted_local_path

        if remote_path:
            formatted_remote_path = uppercase_drive_letter(
                force_suffix(abspath(remote_path))
            )

            if not _remote_folder_is_valid(
                data['external_download_client_id'],
                formatted_remote_path, data['id']
            ):
                raise RemoteMappingInvalid(remote_path)

            data['remote_path'] = formatted_remote_path

        try:
            get_db().execute("""
                UPDATE remote_mappings
                SET
                    external_download_client_id = :external_download_client_id,
                    remote_path = :remote_path,
                    local_path = :local_path
                WHERE id = :id;
                """,
                {
                    **data,
                    "id": self.id
                }
            )

        except IntegrityError:
            # External download client ID is invalid
            raise ExternalClientNotFound(external_download_client_id or -1)

        return self.get()

    def delete(self) -> None:
        """Delete the mapping"""
        LOGGER.info(f'Deleting remote mapping {self.id}')
        get_db().execute(
            "DELETE FROM remote_mappings WHERE id = ?;",
            (self.id,)
        )
        return


class RemoteMappings:
    @classmethod
    def get_all(cls) -> List[RemoteMappingData]:
        """Get the data of all mappings.

        Returns:
            List[RemoteMappingData]: A list of the data of all mappings.
        """
        result: List[RemoteMappingData] = [
            cast(RemoteMappingData, m)
            for m in get_db().execute("""
                SELECT id, external_download_client_id, remote_path, local_path
                FROM remote_mappings;
            """).fetchalldict()
        ]
        return result

    @classmethod
    def get_one(cls, mapping_id: int) -> RemoteMapping:
        """Get a mapping based on its ID.

        Args:
            mapping_id (int): The ID of the mapping to get.

        Raises:
            RemoteMappingNotFound: Mapping with given ID does not exist.

        Returns:
            RemoteMapping: The mapping.
        """
        return RemoteMapping(mapping_id)

    @classmethod
    def local_to_remote(
        cls,
        external_download_client_id: int,
        path: str
    ) -> str:
        """Translate a path from Kapowarr to one for the external download
        client. Returns original path if no mapping matches.

        Args:
            external_download_client_id (int): The ID of the external download
                client.
            path (str): The path to translate.

        Returns:
            str: The translated path.
        """
        local_to_remote = get_db().execute("""
            SELECT local_path, remote_path
            FROM remote_mappings
            WHERE
                external_download_client_id = ?
                AND ? LIKE local_path || '%'
            LIMIT 1;
            """,
            (external_download_client_id, path)
        ).fetchone()

        if not local_to_remote:
            return path

        return local_to_remote[1] + path[len(local_to_remote[0]):]

    @classmethod
    def remote_to_local(
        cls,
        external_download_client_id: int,
        path: str
    ) -> str:
        """Translate a path from the external download client to one for
        Kapowarr. Returns original path if no mapping matches.

        Args:
            external_download_client_id (int): The ID of the external download
                client.
            path (str): The path to translate.

        Returns:
            str: The translated path.
        """
        remote_to_local = get_db().execute("""
            SELECT remote_path, local_path
            FROM remote_mappings
            WHERE
                external_download_client_id = ?
                AND ? LIKE remote_path || '%'
            LIMIT 1;
            """,
            (external_download_client_id, path)
        ).fetchone()

        if not remote_to_local:
            return path

        return remote_to_local[1] + path[len(remote_to_local[0]):]

    @classmethod
    def add(
        cls,
        external_download_client_id: int,
        remote_path: str,
        local_path: str
    ) -> RemoteMapping:
        """Add a remote mapping.

        Args:
            external_download_client_id (int): The ID of the external download
                client that the mapping is for.
            remote_path (str): The path how the external client sees it.
            local_path (str): The path how Kapowarr sees it.

        Raises:
            FolderNotFound: The local path could not be found.
            ExternalClientNotFound: External download client with given ID does
                not exist.
            RemoteMappingInvalid: The local path or remote path is a child or
                parent of another local/remote path for the client.

        Returns:
            RemoteMapping: The new mapping.
        """
        LOGGER.info(
            f'Adding remote mapping: {external_download_client_id=}, '
            f'{remote_path=}, {local_path=}'
        )

        formatted_local_path = uppercase_drive_letter(
            force_suffix(abspath(local_path))
        )
        formatted_remote_path = uppercase_drive_letter(
            force_suffix(abspath(remote_path))
        )

        if not isdir(formatted_local_path):
            raise FolderNotFound(local_path)

        if not _local_folder_is_valid(
            external_download_client_id, formatted_local_path
        ):
            raise RemoteMappingInvalid(local_path)

        if not _remote_folder_is_valid(
            external_download_client_id, formatted_remote_path
        ):
            raise RemoteMappingInvalid(remote_path)

        try:
            mapping_id = get_db().execute("""
                INSERT INTO remote_mappings(
                    external_download_client_id, remote_path, local_path
                ) VALUES (
                    :external_download_client_id,
                    :remote_path,
                    :local_path
                );
                """,
                {
                    "external_download_client_id": external_download_client_id,
                    "remote_path": formatted_remote_path,
                    "local_path": formatted_local_path
                }
            ).lastrowid

        except IntegrityError:
            # External download client ID is invalid
            raise ExternalClientNotFound(external_download_client_id)

        LOGGER.debug(f'Adding remote mapping result: {mapping_id}')
        return cls.get_one(mapping_id)
