# -*- coding: utf-8 -*-

from os import mkdir
from os.path import abspath, isdir, samefile, sep as path_sep
from shutil import disk_usage
from sqlite3 import IntegrityError
from typing import List

from backend.custom_exceptions import (FolderNotFound, RootFolderInUse,
                                       RootFolderInvalid, RootFolderNotFound)
from backend.db import get_db
from backend.file_extraction import alphabet
from backend.files import folder_is_inside_folder
from backend.helpers import first_of_column
from backend.logging import LOGGER


class RootFolders:
    cache = {}

    def get_all(self, use_cache: bool = True) -> List[dict]:
        """Get all rootfolders

        Args:
            use_cache (bool, optional): Wether or not to pull data from
            cache instead of going to the database.
                Defaults to True.

        Returns:
            List[dict]: The list of rootfolders
        """
        if not use_cache or not self.cache:
            root_folders = get_db(dict).execute(
                "SELECT id, folder FROM root_folders;"
            )
            self.cache = {
                r['id']: {
                    **dict(r),
                    'size': dict(zip(
                        ('total', 'used', 'free'),
                        disk_usage(r['folder'])
                    ))
                }
                for r in root_folders
            }
        return list(self.cache.values())

    def get_one(self, root_folder_id: int, use_cache: bool = True) -> dict:
        """Get a rootfolder based on it's id.

        Args:
            root_folder_id (int): The id of the rootfolder to get.

            use_cache (bool, optional): Wether or not to pull data from
            cache instead of going to the database.
                Defaults to True.

        Raises:
            RootFolderNotFound: The id doesn't map to any rootfolder.
                Could also be because of cache being behind database.

        Returns:
            dict: The rootfolder info
        """
        if not use_cache or not self.cache:
            self.get_all(use_cache=False)
        root_folder = self.cache.get(root_folder_id)
        if not root_folder:
            raise RootFolderNotFound
        return root_folder

    def __getitem__(self, root_folder_id: int) -> str:
        return self.get_one(root_folder_id)['folder']

    def __setitem__(self, root_folder_id: int, new_folder: str) -> None:
        self.rename(root_folder_id, new_folder)
        return

    def add(self, folder: str) -> dict:
        """Add a rootfolder

        Args:
            folder (str): The folder to add

        Raises:
            FolderNotFound: The folder doesn't exist
            RootFolderInvalid: The folder is not allowed

        Returns:
            dict: The rootfolder info
        """
        # Format folder and check if it exists
        LOGGER.info(f'Adding rootfolder from {folder}')
        if not isdir(folder):
            raise FolderNotFound
        folder = abspath(folder) + path_sep

        if (
            len(folder) >= 4
            and folder[1:3] == ":\\"
            and folder[0].lower() in alphabet
        ):
            folder = folder[0].upper() + folder[1:]

        for current_rf in self.get_all():
            if (
                folder_is_inside_folder(current_rf['folder'], folder)
                or folder_is_inside_folder(folder, current_rf['folder'])
            ):
                raise RootFolderInvalid

        # Insert into database
        root_folder_id = get_db(dict).execute(
            "INSERT INTO root_folders(folder) VALUES (?)",
            (folder,)
        ).lastrowid

        root_folder = self.get_one(root_folder_id, use_cache=False)

        LOGGER.debug(f'Adding rootfolder result: {root_folder_id}')
        return root_folder

    def rename(self, root_folder_id: int, new_folder: str) -> dict:
        """Rename a root folder.

        Args:
            root_folder_id (int): The ID of the current root folder, to rename.
            new_folder (str): The new folderpath for the root folder.

        Raises:
            RootFolderInvalid: The folder is not allowed.

        Returns:
            dict: The rootfolder info
        """
        from backend.volumes import Volume

        if not isdir(new_folder):
            mkdir(new_folder)

        if samefile(self[root_folder_id], new_folder):
            return self.get_one(root_folder_id)

        LOGGER.info(
            f'Renaming root folder {self[root_folder_id]} ({root_folder_id}) '
            f'to {new_folder}'
        )
        new_id: int = self.add(new_folder)['id']

        cursor = get_db()
        volume_ids: List[int] = first_of_column(cursor.execute(
            "SELECT id FROM volumes WHERE root_folder = ?;",
            (root_folder_id,)
        ))

        for volume_id in volume_ids:
            Volume(volume_id, check_existence=False)['root_folder'] = new_id

        cursor.executescript(f"""
            PRAGMA foreign_keys = OFF;

            DELETE FROM root_folders WHERE id = {root_folder_id};
            UPDATE root_folders SET id = {root_folder_id} WHERE id = {new_id};
            UPDATE volumes SET root_folder = {root_folder_id} WHERE root_folder = {new_id};

            PRAGMA foreign_keys = ON;
        """)
        return self.get_one(root_folder_id, use_cache=False)

    def delete(self, root_folder_id: int) -> None:
        """Delete a rootfolder

        Args:
            root_folder_idd (int): The id of the rootfolder to delete

        Raises:
            RootFolderNotFound: The id doesn't map to any rootfolder
            RootFolderInUse: The rootfolder is still in use by a volume
        """
        LOGGER.info(f'Deleting rootfolder {root_folder_id}')
        cursor = get_db()

        # Remove from database
        try:
            if not cursor.execute(
                "DELETE FROM root_folders WHERE id = ?", (root_folder_id,)
            ).rowcount:
                raise RootFolderNotFound
        except IntegrityError:
            raise RootFolderInUse

        self.get_all(use_cache=False)
        return
