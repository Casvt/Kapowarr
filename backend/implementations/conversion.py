# -*- coding: utf-8 -*-

"""
Converting files to a different format
"""

from functools import lru_cache
from itertools import chain
from os.path import splitext
from typing import Dict, List, Set, Type, Union
from zipfile import ZipFile

from backend.base.definitions import FileConstants, FileConverter
from backend.base.helpers import PortablePool, filtered_iter, get_subclasses
from backend.base.logging import LOGGER
from backend.implementations.converters import run_rar
from backend.implementations.volumes import Volume, scan_files
from backend.internals.db import commit
from backend.internals.server import WebSocket
from backend.internals.settings import Settings


def archive_contains_issues(archive_file: str) -> bool:
    """Check if an archive file contains full issues or if the whole archive
    is one single issue.

    Args:
        archive_file (str): The archive file to check. Must have the zip or rar
        extension.

    Returns:
        bool: Whether the archive file contains issue files.
    """
    ext = splitext(archive_file)[1].lower()

    if ext == '.zip':
        with ZipFile(archive_file) as zip:
            namelist = zip.namelist()

    elif ext == '.rar':
        namelist = run_rar([
            "lb", # List archive contents bare
            archive_file # Archive to list contents of
        ]).stdout.split("\n")[:-1]

    else:
        return False

    return any(
        splitext(f)[1].lower() in FileConstants.CONTAINER_EXTENSIONS
        for f in namelist
    )


class FileConversionHandler:
    @staticmethod
    @lru_cache(1)
    def get_conversion_methods() -> Dict[str, Dict[str, Type[FileConverter]]]:
        """Get all converters.

        Returns:
            Dict[str, Dict[str, Type[FileConverter]]]: Mapping of source_format
            to target_format to conversion class.
        """
        conversion_methods = {}
        for fc in get_subclasses(FileConverter):
            conversion_methods.setdefault(
                fc.source_format, {}
            )[fc.target_format] = fc
        return conversion_methods

    @staticmethod
    @lru_cache(1)
    def get_available_formats() -> Set[str]:
        """Get all available formats that can be converted to.

        Returns:
            Set[str]: The list with all formats.
        """
        return set(chain.from_iterable(
            FileConversionHandler.get_conversion_methods().values()
        ))

    def __init__(
        self,
        file: str,
        format_preference: Union[List[str], None] = None
    ) -> None:
        """Prepare file for conversion.

        Args:
            file (str): The file to convert.
            format_preference (Union[List[str], None], optional): Custom format
            preference to use, or `None` to use the one from the settings.
                Defaults to None.
        """
        self.file = file
        self.fp = format_preference or Settings().sv.format_preference
        self.source_format = splitext(file)[1].lstrip('.').lower()
        self.target_format = self.source_format
        self.converter = None

        conversion_methods = self.get_conversion_methods()

        if self.source_format not in conversion_methods:
            return

        available_formats = conversion_methods[self.source_format]
        for format in self.fp:
            if self.source_format == format:
                break

            if format in available_formats:
                self.target_format = available_formats[format].target_format
                self.converter = available_formats[format]
                break

        return


def convert_file(converter: FileConversionHandler) -> List[str]:
    """Convert a file.

    Args:
        converter (FileConversionHandler): The file converter.

    Returns:
        List[str]: The resulting files from the conversion.
    """
    if not converter.converter:
        return [converter.file]

    LOGGER.info(
        f"Converting file from {converter.source_format} to {converter.target_format}: {converter.file}"
    )
    return converter.converter.convert(converter.file)


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
    settings = Settings().get_settings()
    volume = Volume(volume_id)

    extract_issue_ranges = settings.extract_issue_ranges
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
        converter = None

        if (
            extract_issue_ranges
            and splitext(f)[1].lower() in FileConstants.EXTRACTABLE_EXTENSIONS
            and archive_contains_issues(f)
        ):
            converter = FileConversionHandler(f, ['folder']).converter

        if converter is None:
            converter = FileConversionHandler(f).converter

        if converter is not None:
            if converter.target_format == 'folder':
                result[f] = volume_folder
            else:
                result[f] = splitext(f)[0] + '.' + converter.target_format

    return result


def mass_convert(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: List[str] = [],
    update_websocket: bool = False
) -> None:
    """Convert files for a volume or issue.

    Args:
        volume_id (int): The ID of the volume to convert for.

        issue_id (Union[int, None], optional): The ID of the issue to convert for.
            Defaults to None.

        filepath_filter (List[str], optional): Only convert files
        mentioned in this list.
            Defaults to [].

        update_websocket (bool, optional): Send task progress updates over
        the websocket.
            Defaults to False.
    """
    settings = Settings().get_settings()
    volume = Volume(volume_id)

    extract_issue_ranges = settings.extract_issue_ranges

    planned_conversions: List[FileConversionHandler] = []
    for f in filtered_iter(
        (f["filepath"]
        for f in (
            volume.get_all_files()
            if not issue_id else
            volume.get_issue(issue_id).get_files()
        )),
        set(filepath_filter)
    ):
        converted = False
        if (
            extract_issue_ranges
            and splitext(f)[1].lower() in FileConstants.EXTRACTABLE_EXTENSIONS
            and archive_contains_issues(f)
        ):
            converter = FileConversionHandler(f, ['folder'])
            if converter.converter is not None:
                resulting_files = convert_file(converter)
                for file in resulting_files:
                    fch = FileConversionHandler(file)
                    if fch.converter is not None:
                        planned_conversions.append(fch)
                converted = True

        if not converted:
            fch = FileConversionHandler(f)
            if fch.converter is not None:
                planned_conversions.append(fch)

    total_count = len(planned_conversions)

    if total_count == 0:
        return

    elif total_count == 1:
        # Avoid mp overhead when we're only converting one file
        convert_file(planned_conversions[0])

    else:
        # Commit changes because new connections are opened in the processes
        commit()
        with PortablePool(max_processes=total_count) as pool:
            if update_websocket:
                ws = WebSocket()
                ws.update_task_status(
                    message=f'Converted 0/{total_count}'
                )
                for idx, _ in enumerate(pool.imap_unordered(
                    convert_file,
                    planned_conversions
                )):
                    ws.update_task_status(
                        message=f'Converted {idx+1}/{total_count}'
                    )
            else:
                pool.map(
                    convert_file,
                    planned_conversions
                )

    scan_files(volume_id)

    return
