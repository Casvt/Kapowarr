# -*- coding: utf-8 -*-

from typing import Any, Callable, Dict, List, TypeVar

from backend.base.custom_exceptions import (InvalidKeyValue, KeyNotFound,
                                            RootFolderNotFound,
                                            VolumeDownloadedFor)
from backend.base.definitions import MonitorScheme
from backend.base.logging import LOGGER
from backend.features.download_queue import DownloadHandler
from backend.features.search import auto_search
from backend.implementations.conversion import mass_convert
from backend.implementations.file_processing import (mass_set_file_date,
                                                     mass_set_ownership,
                                                     mass_set_permissions)
from backend.implementations.naming import mass_rename
from backend.implementations.root_folders import RootFolders
from backend.implementations.volumes import Volume, refresh_and_scan
from backend.internals.db import iter_commit
from backend.internals.server import MassEditorStatusEvent, WebSocket

ActionCallable = Callable[[List[int], str, Dict[str, Any]], None]


ActionType = TypeVar(
    "ActionType",
    bound=ActionCallable
)


# region Manager
class MassEditorActionManager:
    actions: Dict[str, ActionCallable] = {}

    @classmethod
    def register_action(cls, identifier: str):
        def wrapper(action: ActionType) -> ActionType:
            if identifier in cls.actions:
                raise RuntimeError(
                    f"Mass Editor action with {identifier=} "
                    "registered multiple times"
                )
            cls.actions[identifier] = action
            return action
        return wrapper

    @classmethod
    def run_action(
        cls,
        action: str,
        volume_ids: List[int],
        **kwargs: Any
    ) -> None:
        try:
            action_runner = cls.actions[action]
        except KeyError:
            raise InvalidKeyValue("action", action)

        LOGGER.info(
            f"Running mass editor action '{action}' on volumes: {volume_ids}"
        )
        action_runner(volume_ids, action, kwargs)
        return


# region Actions
@MassEditorActionManager.register_action('delete')
def mass_editor_delete(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    delete_volume_folder = kwargs.get('delete_folder', False)
    if not isinstance(delete_volume_folder, bool):
        raise InvalidKeyValue('delete_folder', delete_volume_folder)

    ws = WebSocket()
    total_items = len(volume_ids)

    for item_index, volume_id in enumerate(iter_commit(volume_ids)):
        ws.emit(MassEditorStatusEvent(
            identifier,
            item_index + 1,
            total_items
        ))

        try:
            Volume(volume_id).delete(delete_volume_folder)
        except VolumeDownloadedFor:
            continue

    return


@MassEditorActionManager.register_action('root_folder')
def mass_editor_root_folder(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    root_folder_id = kwargs.get('root_folder_id')
    if root_folder_id is None:
        raise KeyNotFound('root_folder_id')
    if not isinstance(root_folder_id, int):
        raise InvalidKeyValue('root_folder_id', root_folder_id)
    # Raises RootFolderNotFound if ID is invalid
    if not RootFolders().is_id_valid(root_folder_id):
        raise RootFolderNotFound(root_folder_id)

    LOGGER.info(f"Using mass editor, setting root folder to {root_folder_id}")

    ws = WebSocket()
    total_items = len(volume_ids)

    for item_index, volume_id in enumerate(iter_commit(volume_ids)):
        ws.emit(MassEditorStatusEvent(
            identifier,
            item_index + 1,
            total_items
        ))

        Volume(volume_id).change_root_folder(root_folder_id)

    return


@MassEditorActionManager.register_action('rename')
def mass_editor_rename(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    ws = WebSocket()
    total_items = len(volume_ids)

    for item_index, volume_id in enumerate(iter_commit(volume_ids)):
        ws.emit(MassEditorStatusEvent(
            identifier,
            item_index + 1,
            total_items
        ))

        mass_rename(volume_id)

    return


@MassEditorActionManager.register_action('update')
def mass_editor_update(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    ws = WebSocket()
    total_items = len(volume_ids)

    for item_index, volume_id in enumerate(iter_commit(volume_ids)):
        ws.emit(MassEditorStatusEvent(
            identifier,
            item_index + 1,
            total_items
        ))

        try:
            refresh_and_scan(volume_id)
        except InvalidKeyValue:
            # API key invalid
            break

    return


@MassEditorActionManager.register_action('search')
def mass_editor_search(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    download_handler = DownloadHandler()
    ws = WebSocket()
    total_items = len(volume_ids)

    for item_index, volume_id in enumerate(iter_commit(volume_ids)):
        ws.emit(MassEditorStatusEvent(
            identifier,
            item_index + 1,
            total_items
        ))

        search_results = auto_search(volume_id)
        download_handler.add_multiple(
            (result['link'], result["indexer_id"], volume_id, None, False)
            for result in search_results
        )

    return


@MassEditorActionManager.register_action('convert')
def mass_editor_convert(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    ws = WebSocket()
    total_items = len(volume_ids)

    for item_index, volume_id in enumerate(iter_commit(volume_ids)):
        ws.emit(MassEditorStatusEvent(
            identifier,
            item_index + 1,
            total_items
        ))

        mass_convert(volume_id)
    return


@MassEditorActionManager.register_action('unmonitor')
def mass_editor_unmonitor(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    for volume_id in volume_ids:
        Volume(volume_id).update({'monitored': False})

    return


@MassEditorActionManager.register_action('monitor')
def mass_editor_monitor(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    for volume_id in volume_ids:
        Volume(volume_id).update({'monitored': True})

    return


@MassEditorActionManager.register_action('monitoring_scheme')
def mass_editor_monitoring_scheme(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    monitoring_scheme = kwargs.get('monitoring_scheme')
    if monitoring_scheme is None:
        raise KeyNotFound('monitoring_scheme')
    try:
        monitoring_scheme = MonitorScheme(monitoring_scheme)
    except ValueError:
        raise InvalidKeyValue('monitoring_scheme', monitoring_scheme)

    LOGGER.info(
        f"Using mass editor, applying monitoring scheme {monitoring_scheme.value}"
    )

    for volume_id in volume_ids:
        Volume(volume_id).apply_monitor_scheme(monitoring_scheme)

    return


@MassEditorActionManager.register_action('file_date')
def mass_editor_file_date(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    for volume_id in volume_ids:
        mass_set_file_date(volume_id)

    return


@MassEditorActionManager.register_action('file_permissions')
def mass_editor_file_permissions(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    for volume_id in volume_ids:
        mass_set_permissions(volume_id)

    return


@MassEditorActionManager.register_action('file_ownership')
def mass_editor_file_ownership(
    volume_ids: List[int],
    identifier: str,
    kwargs: Any
) -> None:
    for volume_id in volume_ids:
        mass_set_ownership(volume_id)

    return
