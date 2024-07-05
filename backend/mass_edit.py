# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING, List

from backend.conversion import mass_convert
from backend.custom_exceptions import (InvalidKeyValue, KeyNotFound,
                                       VolumeDownloadedFor)
from backend.db import get_db
from backend.logging import LOGGER
from backend.naming import mass_rename
from backend.root_folders import RootFolders
from backend.search import auto_search
from backend.volumes import Volume, refresh_and_scan

if TYPE_CHECKING:
    from backend.download_queue import DownloadHandler


class MassEditorVariables:
    """
    To avoid import loops, this class is imported to the places where
    it needs a value by seting it as a class variable. That
    way, the value is 'sent back' to here where it can be used.
    """
    download_handler: DownloadHandler = None # type: ignore


def mass_editor_delete(volume_ids: List[int], **kwargs) -> None:
    delete_volume_folder = kwargs.get('delete_folder', False)
    if not isinstance(delete_volume_folder, bool):
        raise InvalidKeyValue('delete_folder', delete_volume_folder)

    LOGGER.info(f'Using mass editor, deleting volumes: {volume_ids}')

    for volume_id in volume_ids:
        try:
            Volume(volume_id).delete(delete_volume_folder)
        except VolumeDownloadedFor:
            continue
    return


def mass_editor_rf(volume_ids: List[int], **kwargs) -> None:
    root_folder_id = kwargs.get('root_folder_id')
    if root_folder_id is None:
        raise KeyNotFound('root_folder_id')
    if not isinstance(root_folder_id, int):
        raise InvalidKeyValue('root_folder_id', root_folder_id)
    # Raises RootFolderNotFound if ID is invalid
    RootFolders().get_one(root_folder_id)

    LOGGER.info(
        f'Using mass editor, settings root folder to {root_folder_id} for volumes: {volume_ids}')

    cursor = get_db()
    for volume_id in volume_ids:
        Volume(volume_id)['root_folder'] = root_folder_id
        # For loads of volumes, this loop can take a long time, blocking the db
        # So commit after each volume to avoid db locking
        cursor.connection.commit()

    return


def mass_editor_rename(volume_ids: List[int], **kwargs) -> None:
    LOGGER.info(f'Using mass editor, renaming volumes: {volume_ids}')
    for volume_id in volume_ids:
        mass_rename(volume_id)
    return


def mass_editor_update(volume_ids: List[int], **kwargs) -> None:
    LOGGER.info(f'Using mass editor, updating volumes: {volume_ids}')
    for volume_id in volume_ids:
        refresh_and_scan(volume_id)
    return


def mass_editor_search(volume_ids: List[int], **kwargs) -> None:
    LOGGER.info(f'Using mass editor, auto searching for volumes: {volume_ids}')
    cursor = get_db()
    for volume_id in volume_ids:
        search_results = auto_search(volume_id)
        for result in search_results:
            MassEditorVariables.download_handler.add(
                result['link'],
                volume_id
            )
            # add() does a write so commit in-between to avoid db locking
            cursor.connection.commit()
    return


def mass_editor_convert(volume_ids: List[int], **kwargs) -> None:
    LOGGER.info(f'Using mass editor, converting for volumes: {volume_ids}')
    for volume_id in volume_ids:
        mass_convert(volume_id)
    return


def mass_editor_unmonitor(volume_ids: List[int], **kwargs) -> None:
    LOGGER.info(f'Using mass editor, unmonitoring volumes: {volume_ids}')
    for volume_id in volume_ids:
        Volume(volume_id)['monitored'] = False
    return


def mass_editor_monitor(volume_ids: List[int], **kwargs) -> None:
    LOGGER.info(f'Using mass editor, monitoring volumes: {volume_ids}')
    for volume_id in volume_ids:
        Volume(volume_id)['monitored'] = True
    return


action_to_func = {
    'delete': mass_editor_delete,
    'root_folder': mass_editor_rf,
    'rename': mass_editor_rename,
    'update': mass_editor_update,
    'search': mass_editor_search,
    'convert': mass_editor_convert,
    'unmonitor': mass_editor_unmonitor,
    'monitor': mass_editor_monitor
}
