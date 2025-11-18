# -*- coding: utf-8 -*-

"""
Converting files to a different format.
"""

from itertools import chain
from os.path import splitext
from typing import Callable, Dict, List, Tuple, Union

from backend.base.helpers import PortablePool, filtered_iter
from backend.base.logging import LOGGER
from backend.implementations.converters import ConvertersManager
from backend.implementations.volumes import Volume, scan_files
from backend.internals.db import commit
from backend.internals.db_models import FilesDB
from backend.internals.server import TaskStatusEvent, WebSocket


def convert_file(
    filepath: str,
    source_format: str,
    target_format: str,
    converter: Callable[[str], List[str]]
) -> List[str]:
    """Convert a file.

    Args:
        filepath (str): The path to the file.
        source_format (str): The format that it currently is.
        target_format (str): The format that it will become.
        converter (Callable[[str], List[str]]): The function that will convert
            the file.

    Returns:
        List[str]: The resulting files from the conversion.
    """
    LOGGER.info(
        f"Converting file from {source_format} to {target_format}: {filepath}"
    )
    return converter(filepath)


def preview_mass_convert(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> Dict[str, str]:
    """Get a list of suggested conversions for a volume or issue.

    Args:
        volume_id (int): The ID of the volume to check for.
        issue_id (Union[int, None], optional): The ID of the issue to check for.
            Defaults to None.

    Returns:
        Dict[str, str]: Mapping of filename before to after conversion.
    """
    volume = Volume(volume_id)
    volume_folder = volume.vd.folder

    result = {}
    for f in sorted((
        f["filepath"]
        for f in (
            volume.get_all_files()
            if not issue_id else
            volume.get_issue(issue_id).get_files()
        )
    )):
        converter = ConvertersManager.select_converter(f)
        if converter is None:
            continue

        if converter[1] == 'folder':
            result[f] = volume_folder
        else:
            result[f] = splitext(f)[0] + '.' + converter[1]

    return result


def mass_convert(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: List[str] = [],
    update_websocket_progress: bool = False,
    update_websocket_files: bool = False
) -> List[str]:
    """Convert files for a volume or issue.

    Args:
        volume_id (int): The ID of the volume to convert for.

        issue_id (Union[int, None], optional): The ID of the issue to convert for.
            Defaults to None.

        filepath_filter (List[str], optional): Only convert files
        mentioned in this list.
            Defaults to [].

        update_websocket_progress (bool, optional): Send task progress updates
        over the websocket.
            Defaults to False.

        update_websocket_files (bool, optional): Send updates on the download
        status of issues over the websocket.
            Defaults to False.

    Returns:
        List[str]: The new filenames, only of files that have been be converted.
    """
    volume = Volume(volume_id)

    planned_conversions: List[Tuple[str, str,
        str, Callable[[str], List[str]]]] = []
    for f in filtered_iter(
        (f["filepath"]
        for f in (
            volume.get_all_files()
            if not issue_id else
            volume.get_issue(issue_id).get_files()
        )),
        set(filepath_filter)
    ):
        converter = ConvertersManager.select_converter(f)
        if converter is None:
            continue

        if converter[1] == 'folder':
            resulting_files = convert_file(f, *converter)
            for file in resulting_files:
                converter = ConvertersManager.select_converter(file)
                if converter is not None:
                    planned_conversions.append((file, *converter))

        else:
            planned_conversions.append((f, *converter))

    total_count = len(planned_conversions)
    result = []
    if not total_count:
        return result

    elif total_count == 1:
        # Avoid mp overhead when we're only converting one file
        result = convert_file(*planned_conversions[0])

    else:
        # Commit changes because new connections are opened in the processes
        commit()
        with PortablePool(max_processes=total_count) as pool:
            if update_websocket_progress:
                ws = WebSocket()
                ws.emit(TaskStatusEvent(
                    f'Converted 0/{total_count}'
                ))
                for idx, iter_result in enumerate(pool.istarmap_unordered(
                    convert_file,
                    planned_conversions
                )):
                    result += iter_result
                    ws.emit(TaskStatusEvent(
                        f'Converted {idx+1}/{total_count}'
                    ))

            else:
                result += chain.from_iterable(pool.starmap(
                    convert_file,
                    planned_conversions
                ))

    FilesDB.delete_filepaths((
        f[0] for f in planned_conversions
    ))
    scan_files(
        volume_id,
        filepath_filter=result,
        update_websocket=update_websocket_files
    )

    return result
