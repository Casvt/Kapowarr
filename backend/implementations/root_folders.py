# -*- coding: utf-8 -*-

from functools import lru_cache
from os.path import abspath, isdir, samefile
from shutil import disk_usage
from sqlite3 import IntegrityError
from typing import Dict, List, Union

from backend.base.custom_exceptions import (FolderNotFound, RootFolderInUse,
                                            RootFolderInvalid,
                                            RootFolderNotFound)
from backend.base.definitions import RootFolder, SizeData
from backend.base.files import (are_folders_colliding, create_folder,
                                uppercase_drive_letter)
from backend.base.helpers import Singleton, first_of_subarrays, force_suffix
from backend.base.logging import LOGGER
from backend.internals.db import get_db
from backend.internals.settings import Settings


class RootFolders(metaclass=Singleton):
    @lru_cache(1)
    def __get_folder_mapping(self) -> Dict[int, str]:
        """Get a mapping of all IDs to folders.

        Returns:
            Dict[int, str]: The mapping.
        """
        result = dict(get_db().execute(
            "SELECT id, folder FROM root_folders;"
        ))
        return result

    def __gather_extra_data(
        self,
        root_folder_id: int,
        root_folder_path: str
    ) -> RootFolder:
        if not isdir(root_folder_path):
            create_folder(root_folder_path)

        try:
            d_usage = SizeData(**dict(zip(
                ("total", "used", "free"),
                disk_usage(root_folder_path)
            )))

        except (FileNotFoundError, PermissionError, OSError):
            d_usage = None

        return RootFolder(root_folder_id, root_folder_path, d_usage)

    def is_id_valid(self, root_folder_id: int) -> bool:
        return root_folder_id in self.__get_folder_mapping()

    def get_folder_list(self) -> List[str]:
        """Get a list of all rootfolders.

        Returns:
            List[str]: The list.
        """
        return list(self.__get_folder_mapping().values())

    def get_all(self) -> List[RootFolder]:
        """Get info on all rootfolders.

        Returns:
            List[RootFolder]: The list of rootfolders.
        """
        return [
            self.__gather_extra_data(id, folder)
            for id, folder in self.__get_folder_mapping().items()
        ]

    def get_one(self, root_folder_id: int) -> RootFolder:
        """Get a rootfolder based on its ID.

        Args:
            root_folder_id (int): The ID of the rootfolder to get.

        Raises:
            RootFolderNotFound: The ID doesn't map to any rootfolder.

        Returns:
            RootFolder: The rootfolder info.
        """
        if not self.is_id_valid(root_folder_id):
            raise RootFolderNotFound(root_folder_id)

        return self.__gather_extra_data(
            root_folder_id,
            self.__get_folder_mapping()[root_folder_id]
        )

    def __getitem__(self, root_folder_id: int) -> str:
        """Get the folder based on the ID.

        Args:
            root_folder_id (int): The ID to get the folder of.

        Raises:
            RootFolderNotFound: The ID doesn't map to any rootfolder.

        Returns:
            str: The folderpath.
        """
        if not self.is_id_valid(root_folder_id):
            raise RootFolderNotFound(root_folder_id)

        return self.__get_folder_mapping()[root_folder_id]

    def add(
        self,
        folder: str,
        _folder_to_skip_check: Union[str, None] = None
    ) -> RootFolder:
        """Add a rootfolder.

        Args:
            folder (str): The folder to add.

            _folder_to_skip_check (Union[str, None], optional): Don't check
                whether the added rootfolder is a parent or child of this folder.
                Defaults to None.

        Raises:
            FolderNotFound: The folder doesn't exist.
            RootFolderInvalid: The folder is not allowed.

        Returns:
            RootFolder: The rootfolder info.
        """
        # Format folder and check if it exists
        LOGGER.info(f'Adding rootfolder from {folder}')

        if not isdir(folder):
            raise FolderNotFound(folder)

        folder = uppercase_drive_letter(
            force_suffix(abspath(folder))
        )

        # New rootfolder can't be child or parent of other root folders
        # or the download folder.
        if are_folders_colliding(
            folder,
            (Settings().sv.download_folder, *self.get_folder_list()),
            _folder_to_skip_check
        ):
            raise RootFolderInvalid(folder)

        root_folder_id = get_db().execute(
            "INSERT INTO root_folders(folder) VALUES (?)",
            (folder,)
        ).lastrowid

        self.__get_folder_mapping.cache_clear()
        root_folder = self.get_one(root_folder_id)

        LOGGER.debug(f'Adding rootfolder result: {root_folder_id}')
        return root_folder

    def rename(self, root_folder_id: int, new_folder: str) -> RootFolder:
        """Rename a rootfolder.

        Args:
            root_folder_id (int): The ID of the rootfolder to rename.
            new_folder (str): The new folderpath for the rootfolder.

        Raises:
            RootFolderInvalid: The folder is not allowed.

        Returns:
            RootFolder: The rootfolder info.
        """
        from backend.implementations.volumes import Volume

        new_folder = uppercase_drive_letter(
            force_suffix(abspath(new_folder))
        )

        create_folder(new_folder)
        current_folder = self[root_folder_id]

        if samefile(current_folder, new_folder):
            # Renaming to itself
            return self.get_one(root_folder_id)

        LOGGER.info(
            f'Renaming rootfolder {current_folder} (ID {root_folder_id}) '
            f'to {new_folder}'
        )

        new_id = self.add(
            new_folder,
            _folder_to_skip_check=current_folder
        ).id

        cursor = get_db()
        volume_ids: List[int] = first_of_subarrays(cursor.execute(
            "SELECT id FROM volumes WHERE root_folder = ?;",
            (root_folder_id,)
        ))

        for volume_id in volume_ids:
            Volume(volume_id).change_root_folder(new_id)

        get_db().executescript(f"""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            DELETE FROM root_folders WHERE id = {root_folder_id};
            UPDATE root_folders SET id = {root_folder_id} WHERE id = {new_id};
            UPDATE volumes SET root_folder = {root_folder_id} WHERE root_folder = {new_id};

            COMMIT;
        """)
        self.__get_folder_mapping.cache_clear()
        return self.get_one(root_folder_id)

    def delete(self, root_folder_id: int) -> None:
        """Delete a rootfolder.

        Args:
            root_folder_id (int): The ID of the rootfolder to delete.

        Raises:
            RootFolderNotFound: The ID doesn't map to any rootfolder.
            RootFolderInUse: The rootfolder is still in use by a volume.
        """
        LOGGER.info(f'Deleting rootfolder {root_folder_id}')
        cursor = get_db()

        try:
            cursor.execute(
                "DELETE FROM root_folders WHERE id = ?;",
                (root_folder_id,)
            )
            if not cursor.rowcount:
                raise RootFolderNotFound(root_folder_id)

        except IntegrityError:
            raise RootFolderInUse(root_folder_id)

        self.__get_folder_mapping.cache_clear()
        return
