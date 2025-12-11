# -*- coding: utf-8 -*-

"""
Contains all the converters for converting from one format to another.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import chain
from os import utime
from os.path import basename, dirname, getmtime, join, splitext
from typing import Dict, List, Set, Union
from zipfile import ZipFile

from backend.base.definitions import Constants, FileConstants, FileConverter
from backend.base.file_extraction import extract_filename_data
from backend.base.files import (archive_contains_issues, create_folder,
                                create_zip_archive,
                                delete_empty_parent_folders,
                                delete_file_folder, generate_archive_folder,
                                list_files, rename_file,
                                set_detected_extension)
from backend.base.helpers import run_rar
from backend.base.logging import LOGGER
from backend.implementations.file_matching import scan_files
from backend.implementations.matching import folder_extraction_filter
from backend.implementations.naming import mass_rename
from backend.implementations.volumes import Volume
from backend.internals.db_models import FilesDB
from backend.internals.settings import Settings


# region Helpers
def extract_files_from_folder(
    source_folder: str,
    volume_id: int
) -> List[str]:
    """Move files out of the source folder in to the volume folder, but only if
    they match to the volume. Otherwise they are deleted. The source folder
    is always deleted afterwards.

    Args:
        source_folder (str): The folder to extract files out of.
        volume_id (int): The ID of the volume for which the files should be.

    Returns:
        List[str]: The filepaths of the files that were extracted.
    """
    folder_contents = list_files(
        source_folder,
        FileConstants.SCANNABLE_EXTENSIONS
    )

    volume = Volume(volume_id)
    volume_data = volume.get_data()
    volume_issues = volume.get_issues()
    end_year = volume.get_ending_year() or volume_data.year

    relevant_files: List[str] = []
    for file in folder_contents:
        # Remove archive extraction folder name from filepath so that
        # extracted series name is correct, if series name is extracted from
        # foldername.
        efd = extract_filename_data(
            file.replace(Constants.ARCHIVE_EXTRACT_FOLDER + '_', ''),
            assume_volume_number=False
        )

        if folder_extraction_filter(efd, volume_data, volume_issues, end_year):
            relevant_files.append(file)

    if not relevant_files:
        LOGGER.warning(
            "No relevant files found in folder. Keeping all media files."
        )
        relevant_files = folder_contents

    LOGGER.debug(f'Relevant files: {relevant_files}')

    # Move matching files to main folder and delete source folder
    # (including non-matching files).
    result = []
    for file in relevant_files:
        if file.endswith(FileConstants.IMAGE_EXTENSIONS):
            dest = join(
                volume_data.folder,
                basename(dirname(file)),
                basename(file)
            )

        else:
            dest = join(
                volume_data.folder,
                basename(file)
            )

        dest = splitext(dest)[0] + splitext(set_detected_extension(file))[1]

        rename_file(file, dest)
        result.append(dest)

    delete_file_folder(source_folder)
    return result


# region Manager
class ProposedConversion:
    def __init__(
        self,
        filepath: str,
        converter: FileConverter,
        target_format: str
    ) -> None:
        """Create a proposal for a conversion of a file.

        Args:
            filepath (str): The file to convert.
            converter (FileConverter): The converter that will convert the file.
            target_format (str): The format that the file will end up being in.
        """
        self.filepath = filepath
        self.source_format = splitext(filepath)[1].lower().lstrip('.')
        self.target_format = target_format
        self.converter = converter

        if target_format == 'folder':
            self.new_filepath = None
        else:
            self.new_filepath = splitext(filepath)[0] + '.' + target_format

        return

    def perform_conversion(self) -> List[str]:
        """Actually do the conversion that is proposed.

        Returns:
            List[str]: The resulting files or directories, in target_format.
        """
        LOGGER.info(
            "Converting file from %s to %s: %s",
            self.source_format, self.target_format, self.filepath
        )
        return self.converter(self.filepath)


class ConvertersManager:
    converters: Dict[str, Dict[str, FileConverter]] = {}

    @classmethod
    def register_converter(cls, source_format: str, target_format: str):
        """Register a file converter.

        Args:
            source_format (str): The file type that it converts _from_. The
                value is the extension in lowercase without the dot-prefix
                (e.g. 'zip').

            target_format (str): The file type that it converts _to_. The value
                is the extension in lowercase without the dot-prefix
                (e.g. 'cbr').

        Raises:
            RuntimeError: The file format is not recognised by Kapowarr, so it
                can't be converted from or to either.
            RuntimeError: A converter from the given source format to the given
                target format is already registered.
        """
        def wrapper(converter: FileConverter):
            if not (
                source_format == 'folder'
                or '.' + source_format in FileConstants.SCANNABLE_EXTENSIONS
            ):
                raise RuntimeError(
                    f"The source format {source_format} is invalid"
                )

            if not (
                target_format == 'folder'
                or '.' + target_format in FileConstants.SCANNABLE_EXTENSIONS
            ):
                raise RuntimeError(
                    f"The target format {target_format} is invalid"
                )

            if (
                source_format in cls.converters
                and target_format in cls.converters[source_format]
            ):
                raise RuntimeError(
                    f"File converter with source format {source_format} "
                    f"and target format {target_format} "
                    "registered multiple times"
                )

            cls.converters.setdefault(
                source_format, {}
            )[target_format] = converter

            return converter

        return wrapper

    @classmethod
    @lru_cache(1)
    def formats_convertible_to_folder(cls) -> List[str]:
        """Get all source formats that can be converted into a folder.

        Returns:
            List[str]: The source formats.
        """
        return [
            source_format
            for source_format, target_format in cls.converters.items()
            if 'folder' in target_format
        ]

    @classmethod
    @lru_cache(1)
    def get_available_formats(cls) -> Set[str]:
        """Get all available formats that can be converted to.

        Returns:
            Set[str]: The list with all formats.
        """
        return set(chain.from_iterable(cls.converters.values()))

    @classmethod
    def select_converter(cls, filepath: str) -> Union[ProposedConversion, None]:
        """Get a proposed conversion for the file, based on the current format
        and the format preference.

        Args:
            filepath (str): The filepath to convert for.

        Returns:
            Union[ProposedConversion, None]: The selected conversion that should
                happen, or `None` if the file should be kept in the current
                format.
        """
        settings = Settings().get_settings()
        source_format = splitext(filepath)[1].lower().lstrip('.')

        if (
            settings.extract_issue_ranges
            and source_format in cls.formats_convertible_to_folder()
            and archive_contains_issues(filepath)
        ):
            # Extract issue files from archive
            return ProposedConversion(
                filepath, cls.converters[source_format]['folder'], 'folder'
            )

        for potential_format in settings.format_preference:
            if source_format == potential_format:
                # File already is most desired, possible, format
                return None

            if potential_format in cls.converters[source_format]:
                # Found format to convert to
                return ProposedConversion(
                    filepath,
                    cls.converters[source_format][potential_format],
                    potential_format
                )

        # Can't convert file to anything that is desired
        return None


# region ZIP
@ConvertersManager.register_converter("zip", "cbz")
def zip_to_cbz(file: str) -> List[str]:
    target = splitext(file)[0] + '.cbz'
    rename_file(
        file,
        target
    )
    return [target]


@ConvertersManager.register_converter("zip", "rar")
def zip_to_rar(file: str) -> List[str]:
    volume_id = FilesDB.volume_of_file(file)
    if not volume_id:
        # File not matched to volume
        return [file]

    volume_folder = Volume(volume_id).vd.folder
    archive_folder = generate_archive_folder(volume_folder, file)

    with ZipFile(file, 'r') as zip:
        zip.extractall(archive_folder)

    run_rar([
        'a', # Add files to archive
        '-ep', # Exclude paths from names
        '-inul', # Disable all messages
        splitext(file)[0], # Ext-less target filename of created archive
        archive_folder # Source folder
    ])

    delete_file_folder(archive_folder)
    delete_file_folder(file)
    delete_empty_parent_folders(dirname(file), volume_folder)

    return [splitext(file)[0] + '.rar']


@ConvertersManager.register_converter("zip", "cbr")
def zip_to_cbr(file: str) -> List[str]:
    rar_file = zip_to_rar(file)[0]
    if rar_file == file:
        # File not matched to volume
        return [file]
    cbr_file = rar_to_cbr(rar_file)
    return cbr_file


@ConvertersManager.register_converter("zip", "folder")
def zip_to_folder(file: str) -> List[str]:
    volume_id = FilesDB.volume_of_file(file)
    if not volume_id:
        # File not matched to volume
        return [file]

    volume_folder = Volume(volume_id).vd.folder
    archive_folder = generate_archive_folder(volume_folder, file)

    with ZipFile(file, 'r') as zip:
        zip.extractall(archive_folder)

    resulting_files = extract_files_from_folder(
        archive_folder,
        volume_id
    )

    if resulting_files:
        scan_files(volume_id, filepath_filter=resulting_files)
        resulting_files = mass_rename(
            volume_id,
            filepath_filter=resulting_files
        )

    delete_file_folder(file)
    delete_empty_parent_folders(dirname(file), volume_folder)

    return resulting_files


# region CBZ
@ConvertersManager.register_converter("cbz", "zip")
def cbz_to_zip(file: str) -> List[str]:
    target = splitext(file)[0] + '.zip'
    rename_file(
        file,
        target
    )
    return [target]


@ConvertersManager.register_converter("cbz", "rar")
def cbz_to_rar(file: str) -> List[str]:
    return zip_to_rar(file)


@ConvertersManager.register_converter("cbz", "cbr")
def cbz_to_cbr(file: str) -> List[str]:
    rar_file = zip_to_rar(file)[0]
    if rar_file == file:
        # File not matched to volume
        return [file]
    cbr_file = rar_to_cbr(rar_file)
    return cbr_file


@ConvertersManager.register_converter("cbz", "folder")
def cbz_to_folder(file: str) -> List[str]:
    return zip_to_folder(file)


# region RAR
@ConvertersManager.register_converter("rar", "cbr")
def rar_to_cbr(file: str) -> List[str]:
    target = splitext(file)[0] + '.cbr'
    rename_file(
        file,
        target
    )
    return [target]


@ConvertersManager.register_converter("rar", "zip")
def rar_to_zip(file: str) -> List[str]:
    volume_id = FilesDB.volume_of_file(file)
    if not volume_id:
        # File not matched to volume
        return [file]

    volume_folder = Volume(volume_id).vd.folder
    archive_folder = generate_archive_folder(volume_folder, file)
    create_folder(archive_folder)

    run_rar([
        'x', # Extract files with full path
        '-inul', # Disable all messages
        file, # Source archive file
        archive_folder # Target folder to extract into
    ])

    # Files that are put in a ZIP file have to have a minimum last
    # modification time.
    for f in list_files(archive_folder):
        if getmtime(f) <= Constants.ZIP_MIN_MOD_TIME:
            utime(
                f,
                (Constants.ZIP_MIN_MOD_TIME, Constants.ZIP_MIN_MOD_TIME)
            )

    target_file = splitext(file)[0] + '.zip'
    create_zip_archive(archive_folder, target_file)

    delete_file_folder(archive_folder)
    delete_file_folder(file)
    delete_empty_parent_folders(dirname(file), volume_folder)

    return [target_file]


@ConvertersManager.register_converter("rar", "cbz")
def rar_to_cbz(file: str) -> List[str]:
    zip_file = rar_to_zip(file)[0]
    if zip_file == file:
        # File not matched to volume
        return [file]
    cbz_file = zip_to_cbz(zip_file)
    return cbz_file


@ConvertersManager.register_converter("rar", "folder")
def rar_to_folder(file: str) -> List[str]:
    volume_id = FilesDB.volume_of_file(file)
    if not volume_id:
        # File not matched to volume
        return [file]

    volume_folder = Volume(volume_id).vd.folder
    archive_folder = generate_archive_folder(volume_folder, file)
    create_folder(archive_folder)

    run_rar([
        'x', # Extract files with full path
        '-inul', # Disable all messages
        file, # Source archive file
        archive_folder # Target folder to extract into
    ])

    resulting_files = extract_files_from_folder(
        archive_folder,
        volume_id
    )

    if resulting_files:
        scan_files(volume_id, filepath_filter=resulting_files)
        resulting_files = mass_rename(
            volume_id,
            filepath_filter=resulting_files
        )

    delete_file_folder(file)
    delete_empty_parent_folders(dirname(file), volume_folder)

    return resulting_files


# region CBR
@ConvertersManager.register_converter("cbr", "rar")
def cbr_to_rar(file: str) -> List[str]:
    target = splitext(file)[0] + '.rar'
    rename_file(
        file,
        target
    )
    return [target]


@ConvertersManager.register_converter("cbr", "zip")
def cbr_to_zip(file: str) -> List[str]:
    return rar_to_zip(file)


@ConvertersManager.register_converter("cbr", "cbz")
def cbr_to_cbz(file: str) -> List[str]:
    zip_file = rar_to_zip(file)[0]
    if zip_file == file:
        # File not matched to volume
        return [file]
    cbz_file = zip_to_cbz(zip_file)
    return cbz_file


@ConvertersManager.register_converter("cbr", "folder")
def cbr_to_folder(file: str) -> List[str]:
    return rar_to_folder(file)
