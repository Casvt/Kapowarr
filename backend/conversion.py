# -*- coding: utf-8 -*-

"""
Converting files to a different format
"""

from itertools import chain
from multiprocessing import cpu_count
from os.path import splitext
from sys import platform
from typing import Dict, Iterable, List, Set, Tuple, Type, Union
from zipfile import ZipFile

from backend.converters import FileConverter, get_rar_output, rar_executables
from backend.db import get_db
from backend.file_extraction import archive_extensions, container_extensions
from backend.helpers import PortablePool
from backend.server import WebSocket
from backend.settings import Settings
from backend.volumes import Volume, scan_files

conversion_methods: Dict[str, Dict[str, Type[FileConverter]]] = {}
"source_format -> target_format -> conversion class"
for fc in FileConverter.__subclasses__():
    conversion_methods.setdefault(fc.source_format, {})[fc.target_format] = fc


def get_available_formats() -> Set[str]:
    """Get all available formats that can be converted to.

    Returns:
        Set[str]: The list with all formats
    """
    return set(chain.from_iterable(conversion_methods.values()))


def find_target_format_file(
    file: str,
    formats: Iterable[str]
) -> Union[Type[FileConverter], None]:
    """Get a FileConverter class based on source format and desired formats.

    Args:
        file (str): The file to get the converter for.
        formats (Iterable[str]): The formats to convert to, in order of preference.

    Returns:
        Union[Type[FileConverter], None]: The converter class that is possible
        and most prefered.
            In case of no possible conversion, `None` is returned.
    """
    source_format = splitext(file)[1].lstrip('.').lower()

    if source_format not in conversion_methods:
        return

    if (
        source_format in ('rar', 'cbr')
        and platform not in rar_executables
    ):
        return

    available_formats = conversion_methods[source_format]

    for format in formats:
        if source_format == format:
            break

        if format in available_formats:
            return available_formats[format]

    return


def convert_file(
    file: str,
    formats: Iterable[str]
) -> Union[str, List[str]]:
    """Convert a file from one format to another.

    Args:
        file (str): The file to convert.

        formats (Iterable[str]): A iterable of formats to convert the file to.
            Order of list is preference of format (left to right).

            Should be key `conversion.conversion_methods` -> source_format dict.

    Returns:
        Union[str, List[str]]: The path of the converted file.
    """
    conversion_class = find_target_format_file(
        file,
        formats
    )
    if conversion_class is not None:
        return conversion_class.convert(file)
    else:
        return file


def map_convert_file(a: Tuple[str, Iterable[str]]) -> Union[str, List[str]]:
    return convert_file(*a)


def archive_contains_issues(archive_file: str) -> bool:
    """Check if an archive file contains full issues or if the whole archive
    is one single issue.

    Args:
        archive_file (str): The archive file to check. Must have the zip or rar
        extension.

    Returns:
        bool: Whether or not the archive file contains issue files.
    """
    ext = splitext(archive_file)[1].lower()

    if ext == '.zip':
        with ZipFile(archive_file) as zip:
            namelist = zip.namelist()

    elif ext == '.rar' and platform in rar_executables:
        namelist = get_rar_output([
            "lb",
            archive_file
        ]).split("\n")[:-1]

    else:
        return False

    return any(
        splitext(f)[1].lower() in container_extensions
        for f in namelist
    )


def preview_mass_convert(
    volume_id: int,
    issue_id: Union[int, None] = None
) -> List[Dict[str, str]]:
    """Get a list of suggested conversions for a volume or issue

    Args:
        volume_id (int): The ID of the volume to check for.
        issue_id (Union[int, None], optional): The ID of the issue to check for.
            Defaults to None.

    Returns:
        List[Dict[str, str]]: The list of suggestions.
            Dicts have the keys `before` and `after`.
    """
    settings = Settings()
    volume = Volume(volume_id)

    format_preference = settings['format_preference']
    extract_issue_ranges = settings['extract_issue_ranges']
    volume_folder = volume['folder']

    result = []
    for f in sorted((f["filepath"] for f in volume.get_files(issue_id))):
        converter = None

        if (
            extract_issue_ranges
            and splitext(f)[1].lower() in archive_extensions
            and archive_contains_issues(f)
        ):
            converter = find_target_format_file(
                f,
                ['folder']
            )

        if converter is None:
            converter = find_target_format_file(
                f,
                format_preference
            )

        if converter is not None:
            if converter.target_format == 'folder':
                result.append({
                    'before': f,
                    'after': volume_folder
                })
            else:
                result.append({
                    'before': f,
                    'after': splitext(f)[0] + '.' + converter.target_format
                })

    return result


def mass_convert(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None,
    update_websocket: bool = False
) -> None:
    """Convert files for a volume or issue.

    Args:
        volume_id (int): The ID of the volume to convert for.

        issue_id (Union[int, None], optional): The ID of the issue to convert for.
            Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only convert files
        mentioned in this list.
            Defaults to None.

        update_websocket (bool, optional): Send task progress updates over
        the websocket.
            Defaults to False.
    """
    # We're checking a lot if strings are in this list,
    # so making it a set will increase performance (due to hashing).
    hashed_files = set(filepath_filter or [])

    settings = Settings()
    volume = Volume(volume_id)

    format_preference = settings['format_preference']
    extract_issue_ranges = settings['extract_issue_ranges']

    planned_conversions: List[Tuple[str, List[str]]] = []
    for f in (f["filepath"] for f in volume.get_files(issue_id)):
        if hashed_files and f not in hashed_files:
            continue

        converted = False
        if (
            extract_issue_ranges
            and splitext(f)[1].lower() in archive_extensions
            and archive_contains_issues(f)
        ):
            converter = find_target_format_file(
                f,
                ['folder']
            )
            if converter is not None:
                resulting_files = converter.convert(f)
                for file in resulting_files:
                    planned_conversions.append(
                        (file, format_preference)
                    )
                converted = True

        if not converted:
            planned_conversions.append(
                (f, format_preference)
            )

    # Don't start more processes than files, but also not
    # more than that is supported by the CPU
    processes = min(len(planned_conversions), cpu_count())

    if processes == 0:
        return

    elif processes == 1:
        # Avoid mp overhead when we're only converting one file
        convert_file(
            *planned_conversions[0]
        )

    else:
        # Commit changes because new connections are opened in the processes
        get_db().connection.commit()
        with PortablePool(processes=processes) as pool:
            if update_websocket:
                ws = WebSocket()
                completed = 0
                total = len(planned_conversions)
                ws.update_task_status(
                    message=f'Converted {completed}/{total}'
                )
                for _ in pool.imap_unordered(
                    map_convert_file,
                    planned_conversions
                ):
                    completed += 1
                    ws.update_task_status(
                        message=f'Converted {completed}/{total}'
                    )
            else:
                pool.starmap(
                    convert_file,
                    planned_conversions
                )

    scan_files(volume_id)

    return
