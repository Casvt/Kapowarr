# -*- coding: utf-8 -*-

from os.path import abspath, isdir, samefile
from shutil import disk_usage
from sqlite3 import IntegrityError
from typing import Dict, List

from git import Union

from backend.base.custom_exceptions import (FolderNotFound, RootFolderInUse,
                                            RootFolderInvalid,
                                            RootFolderNotFound)
from backend.base.definitions import RootFolder, SizeData
from backend.base.files import (create_folder, folder_is_inside_folder,
                                uppercase_drive_letter)
from backend.base.helpers import Singleton, first_of_column, force_suffix
from backend.base.logging import LOGGER
from backend.internals.db import get_db
from backend.internals.settings import Settings


class RootFolders(metaclass=Singleton):
    cache: Dict[int, RootFolder] = {}

    def __init__(self) -> None:
        if not self.cache:
            self._load_cache()
        return

    def _load_cache(self) -> None:
        """Update the cache."""
        root_folders = get_db().execute(
            "SELECT id, folder FROM root_folders;"
        )
        self.cache = {
            r['id']: RootFolder(
                r["id"],
                r["folder"],
                SizeData(**dict(zip(
                    ('total', 'used', 'free'),
                    disk_usage(r['folder'])
                )))
            )
            for r in root_folders
        }
        return

    def get_all(self) -> List[RootFolder]:
        """Get all rootfolders.

        Returns:
            List[RootFolder]: The list of rootfolders.
        """
        return list(self.cache.values())

    def get_one(self, root_folder_id: int) -> RootFolder:
        """Get a rootfolder based on it's id.

        Args:
            root_folder_id (int): The id of the rootfolder to get.

        Raises:
            RootFolderNotFound: The id doesn't map to any rootfolder.
                Could also be because of cache being behind database.

        Returns:
            RootFolder: The rootfolder info.
        """
        root_folder = self.cache.get(root_folder_id)

        if not root_folder:
            raise RootFolderNotFound

        return root_folder

    def __getitem__(self, root_folder_id: int) -> str:
        """
        Get folder based on ID. Assumes folder with given ID exists.
        """
        return self.get_one(root_folder_id).folder

    def __setitem__(self, root_folder_id: int, new_folder: str) -> None:
        """
        Rename root folder to given value. Assumes folder with given ID exists.
        """
        self.rename(root_folder_id, new_folder)
        return

    def add(
        self,
        folder: str,
        _exclude_folder_from_check: Union[str, None] = None
    ) -> RootFolder:
        """Add a rootfolder.

        Args:
            folder (str): The folder to add.

            _exclude_folder_from_check (Union[str, None], optional): Don't check
            whether the added root folder is a parent or child of this folder.
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
            raise FolderNotFound

        folder = uppercase_drive_letter(
            force_suffix(abspath(folder))
        )

        # New root folder can not be in, or be a parent of,
        # other root folders or the download folder.
        other_folders = (
            *(
                f.folder
                for f in self.get_all()
                if (
                    not _exclude_folder_from_check
                    or f.folder != _exclude_folder_from_check
                )
            ),
            Settings().sv.download_folder
        )
        for other_folder in other_folders:
            if (
                folder_is_inside_folder(other_folder, folder)
                or folder_is_inside_folder(folder, other_folder)
            ):
                raise RootFolderInvalid

        root_folder_id = get_db().execute(
            "INSERT INTO root_folders(folder) VALUES (?)",
            (folder,)
        ).lastrowid

        self._load_cache()
        root_folder = self.get_one(root_folder_id)

        LOGGER.debug(f'Adding rootfolder result: {root_folder_id}')
        return root_folder

    def rename(self, root_folder_id: int, new_folder: str) -> RootFolder:
        """Rename a root folder.

        Args:
            root_folder_id (int): The ID of the current root folder, to rename.
            new_folder (str): The new folderpath for the root folder.

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
            f'Renaming root folder {self[root_folder_id]} (ID {root_folder_id}) '
            f'to {new_folder}')

        new_id = self.add(
            new_folder,
            _exclude_folder_from_check=current_folder
        ).id

        cursor = get_db()
        volume_ids: List[int] = first_of_column(cursor.execute(
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
        self._load_cache()
        return self.get_one(root_folder_id)

    def delete(self, root_folder_id: int) -> None:
        """Delete a rootfolder

        Args:
            root_folder_idd (int): The id of the rootfolder to delete

        Raises:
            RootFolderNotFound: The id doesn't map to any rootfolder
            RootFolderInUse: The rootfolder is still in use by a volume
        """
        LOGGER.info(f'Deleting rootfolder {root_folder_id}')

        # Remove from database
        cursor = get_db()
        try:
            cursor.execute(
                "DELETE FROM root_folders WHERE id = ?", (root_folder_id,)
            )
            if not cursor.rowcount:
                raise RootFolderNotFound
        except IntegrityError:
            raise RootFolderInUse

        self._load_cache()
        return
