# -*- coding: utf-8 -*-

from typing import List

from backend.base.custom_exceptions import (InvalidKeyValue, KeyNotFound,
                                            VolumeDownloadedFor)
from backend.base.definitions import MassEditorAction, MonitorScheme
from backend.base.helpers import get_subclasses
from backend.base.logging import LOGGER
from backend.features.download_queue import DownloadHandler
from backend.features.search import auto_search
from backend.implementations.conversion import mass_convert
from backend.implementations.naming import mass_rename
from backend.implementations.root_folders import RootFolders
from backend.implementations.volumes import Volume, refresh_and_scan
from backend.internals.db import iter_commit


class MassEditorDelete(MassEditorAction):
    identifier = 'delete'

    def run(self, **kwargs) -> None:
        delete_volume_folder = kwargs.get('delete_folder', False)
        if not isinstance(delete_volume_folder, bool):
            raise InvalidKeyValue('delete_folder', delete_volume_folder)

        LOGGER.info(f'Using mass editor, deleting volumes: {self.volume_ids}')

        for volume_id in iter_commit(self.volume_ids):
            try:
                Volume(volume_id).delete(delete_volume_folder)
            except VolumeDownloadedFor:
                continue
        return


class MassEditorRootFolder(MassEditorAction):
    identifier = 'root_folder'

    def run(self, **kwargs) -> None:
        root_folder_id = kwargs.get('root_folder_id')
        if root_folder_id is None:
            raise KeyNotFound('root_folder_id')
        if not isinstance(root_folder_id, int):
            raise InvalidKeyValue('root_folder_id', root_folder_id)
        # Raises RootFolderNotFound if ID is invalid
        RootFolders().get_one(root_folder_id)

        LOGGER.info(
            f'Using mass editor, settings root folder to {root_folder_id} for volumes: {self.volume_ids}'
        )

        for volume_id in iter_commit(self.volume_ids):
            Volume(volume_id).change_root_folder(root_folder_id)

        return


class MassEditorRename(MassEditorAction):
    identifier = 'rename'

    def run(self, **kwargs) -> None:
        LOGGER.info(f'Using mass editor, renaming volumes: {self.volume_ids}')
        for volume_id in iter_commit(self.volume_ids):
            mass_rename(volume_id)
        return


class MassEditorUpdate(MassEditorAction):
    identifier = 'update'

    def run(self, **kwargs) -> None:
        LOGGER.info(f'Using mass editor, updating volumes: {self.volume_ids}')
        for volume_id in iter_commit(self.volume_ids):
            refresh_and_scan(volume_id)
        return


class MassEditorSearch(MassEditorAction):
    identifier = 'search'

    def run(self, **kwargs) -> None:
        LOGGER.info(
            f'Using mass editor, auto searching for volumes: {self.volume_ids}'
        )
        download_handler = DownloadHandler()

        for volume_id in self.volume_ids:
            search_results = auto_search(volume_id)
            download_handler.add_multiple(
                (result['link'], volume_id, None, False)
                for result in search_results
            )

        return


class MassEditorConvert(MassEditorAction):
    identifier = 'convert'

    def run(self, **kwargs) -> None:
        LOGGER.info(
            f'Using mass editor, converting for volumes: {self.volume_ids}')
        for volume_id in iter_commit(self.volume_ids):
            mass_convert(volume_id)
        return


class MassEditorUnmonitor(MassEditorAction):
    identifier = 'unmonitor'

    def run(self, **kwargs) -> None:
        LOGGER.info(
            f'Using mass editor, unmonitoring volumes: {self.volume_ids}')
        for volume_id in self.volume_ids:
            Volume(volume_id)['monitored'] = False
        return


class MassEditorMonitor(MassEditorAction):
    identifier = 'monitor'

    def run(self, **kwargs) -> None:
        LOGGER.info(f'Using mass editor, monitoring volumes: {self.volume_ids}')
        for volume_id in self.volume_ids:
            Volume(volume_id)['monitored'] = True
        return


class MassEditorMonitoringScheme(MassEditorAction):
    identifier = 'monitoring_scheme'

    def run(self, **kwargs) -> None:
        monitoring_scheme = kwargs.get('monitoring_scheme')
        if monitoring_scheme is None:
            raise KeyNotFound('monitoring_scheme')
        try:
            monitoring_scheme = MonitorScheme(monitoring_scheme)
        except ValueError:
            raise InvalidKeyValue('monitoring_scheme', monitoring_scheme)

        LOGGER.info(
            f'Using mass editor, applying monitoring scheme "{monitoring_scheme.value}" for volumes: {self.volume_ids}'
        )

        for volume_id in self.volume_ids:
            Volume(volume_id).apply_monitor_scheme(monitoring_scheme)

        return


def run_mass_editor_action(
    action: str,
    volume_ids: List[int],
    **kwargs
) -> None:
    """Run a mass editor action.

    Args:
        action (str): The action to run.
        volume_ids (List[int]): The volume IDs to run the action on.
        **kwargs (Dict[str, Any]): The arguments to pass to the action.

    Raises:
        InvalidKeyValue: If the action or any argument is not valid.
    """
    for ActionClass in get_subclasses(MassEditorAction):
        if ActionClass.identifier == action:
            break
    else:
        raise InvalidKeyValue('action', action)

    ActionClass(volume_ids).run(**kwargs)
    return
