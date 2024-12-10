# -*- coding: utf-8 -*-

"""
Contains all the converters for converting from one format to another
"""

from __future__ import annotations

from os import utime
from os.path import basename, dirname, getmtime, join, splitext
from shutil import make_archive
from subprocess import run
from sys import platform
from typing import TYPE_CHECKING, List, final
from zipfile import ZipFile

from backend.base.definitions import (SCANNABLE_EXTENSIONS, Constants,
                                      FileConstants, FileConverter)
from backend.base.file_extraction import extract_filename_data
from backend.base.files import (create_folder, delete_empty_parent_folders,
                                delete_file_folder, folder_path,
                                generate_archive_folder, list_files,
                                rename_file)
from backend.base.logging import LOGGER
from backend.implementations.matching import folder_extraction_filter
from backend.implementations.naming import mass_rename
from backend.implementations.volumes import Volume, scan_files
from backend.internals.db_models import FilesDB

if TYPE_CHECKING:
    from subprocess import CompletedProcess


def run_rar(args: List[str]) -> CompletedProcess[str]:
    """Run rar executable. Platform is taken care of inside function.

    Args:
        args (List[str]): The arguments to give to the executable.

    Raises:
        KeyError: Platform not supported.

    Returns:
        CompletedProcess[str]: The result of the process.
    """
    exe = folder_path('backend', 'lib', Constants.RAR_EXECUTABLES[platform])
    return run([exe, *args], capture_output=True, text=True)


def extract_files_from_folder(
    source_folder: str,
    volume_id: int
) -> List[str]:
    """Move files out of folder in to volume folder,
    but only if they match to the volume. Otherwise they are deleted,
    together with the original folder.

    Args:
        source_folder (str): The folder to extract files out of.
        volume_id (int): The ID for which the files should be.

    Returns:
        List[str]: The filepaths of the files that were extracted.
    """
    folder_contents = list_files(
        source_folder,
        SCANNABLE_EXTENSIONS
    )

    volume = Volume(volume_id)
    volume_data = volume.get_data()
    volume_issues = volume.get_issues()
    end_year = volume.get_ending_year() or volume_data.year

    # Filter non-relevant files
    rel_files = [
        c
        for c in folder_contents
        if (
            folder_extraction_filter(
                extract_filename_data(c, False),
                volume_data,
                volume_issues,
                end_year
            )
            and 'variant cover' not in c.lower()
        )
    ]
    LOGGER.debug(f'Relevant files: {rel_files}')

    # Move remaining files to main folder and delete source folder
    result = []
    for c in rel_files:
        if c.endswith(FileConstants.IMAGE_EXTENSIONS):
            dest = join(volume_data.folder, basename(dirname(c)), basename(c))

        else:
            dest = join(volume_data.folder, basename(c))

        rename_file(c, dest)
        result.append(dest)

    delete_file_folder(source_folder)
    return result


# =====================
# region ZIP
# =====================
@final
class ZIPtoCBZ(FileConverter):
    source_format = 'zip'
    target_format = 'cbz'

    @staticmethod
    def convert(file: str) -> List[str]:
        target = splitext(file)[0] + '.cbz'
        rename_file(
            file,
            target
        )
        return [target]


@final
class ZIPtoRAR(FileConverter):
    source_format = 'zip'
    target_format = 'rar'

    @staticmethod
    def convert(file: str) -> List[str]:
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
        delete_empty_parent_folders(dirname(archive_folder), volume_folder)

        return [splitext(file)[0] + '.rar']


@final
class ZIPtoCBR(FileConverter):
    source_format = 'zip'
    target_format = 'cbr'

    @staticmethod
    def convert(file: str) -> List[str]:
        rar_file = ZIPtoRAR.convert(file)[0]
        cbr_file = RARtoCBR.convert(rar_file)
        return cbr_file


@final
class ZIPtoFOLDER(FileConverter):
    source_format = 'zip'
    target_format = 'folder'

    @staticmethod
    def convert(file: str) -> List[str]:
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

        delete_file_folder(archive_folder)
        delete_file_folder(file)
        delete_empty_parent_folders(dirname(file), volume_folder)
        delete_empty_parent_folders(dirname(archive_folder), volume_folder)

        return resulting_files


# =====================
# region CBZ
# =====================
@final
class CBZtoZIP(FileConverter):
    source_format = 'cbz'
    target_format = 'zip'

    @staticmethod
    def convert(file: str) -> List[str]:
        target = splitext(file)[0] + '.zip'
        rename_file(
            file,
            target
        )
        return [target]


@final
class CBZtoRAR(FileConverter):
    source_format = 'cbz'
    target_format = 'rar'

    @staticmethod
    def convert(file: str) -> List[str]:
        return ZIPtoRAR.convert(file)


@final
class CBZtoCBR(FileConverter):
    source_format = 'cbz'
    target_format = 'cbr'

    @staticmethod
    def convert(file: str) -> List[str]:
        rar_file = ZIPtoRAR.convert(file)[0]
        cbr_file = RARtoCBR.convert(rar_file)
        return cbr_file


@final
class CBZtoFOLDER(FileConverter):
    source_format = 'cbz'
    target_format = 'folder'

    @staticmethod
    def convert(file: str) -> List[str]:
        return ZIPtoFOLDER.convert(file)


# =====================
# region RAR
# =====================
@final
class RARtoCBR(FileConverter):
    source_format = 'rar'
    target_format = 'cbr'

    @staticmethod
    def convert(file: str) -> List[str]:
        target = splitext(file)[0] + '.cbr'
        rename_file(
            file,
            target
        )
        return [target]


@final
class RARtoZIP(FileConverter):
    source_format = 'rar'
    target_format = 'zip'

    @staticmethod
    def convert(file: str) -> List[str]:
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

        target_file = splitext(file)[0]
        target_archive = make_archive(target_file, 'zip', archive_folder)

        delete_file_folder(archive_folder)
        delete_file_folder(file)
        delete_empty_parent_folders(dirname(file), volume_folder)
        delete_empty_parent_folders(dirname(archive_folder), volume_folder)

        return [target_archive]


@final
class RARtoCBZ(FileConverter):
    source_format = 'rar'
    target_format = 'cbz'

    @staticmethod
    def convert(file: str) -> List[str]:
        zip_file = RARtoZIP.convert(file)[0]
        cbz_file = ZIPtoCBZ.convert(zip_file)
        return cbz_file


@final
class RARtoFOLDER(FileConverter):
    source_format = 'rar'
    target_format = 'folder'

    @staticmethod
    def convert(file: str) -> List[str]:
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

        delete_file_folder(archive_folder)
        delete_file_folder(file)
        delete_empty_parent_folders(dirname(file), volume_folder)
        delete_empty_parent_folders(dirname(archive_folder), volume_folder)

        return resulting_files


# =====================
# region CBR
# =====================
@final
class CBRtoRAR(FileConverter):
    source_format = 'cbr'
    target_format = 'rar'

    @staticmethod
    def convert(file: str) -> List[str]:
        target = splitext(file)[0] + '.rar'
        rename_file(
            file,
            target
        )
        return [target]


@final
class CBRtoZIP(FileConverter):
    source_format = 'cbr'
    target_format = 'zip'

    @staticmethod
    def convert(file: str) -> List[str]:
        return RARtoZIP.convert(file)


@final
class CBRtoCBZ(FileConverter):
    source_format = 'cbr'
    target_format = 'cbz'

    @staticmethod
    def convert(file: str) -> List[str]:
        zip_file = RARtoZIP.convert(file)[0]
        cbz_file = ZIPtoCBZ.convert(zip_file)
        return cbz_file


@final
class CBRtoFOLDER(FileConverter):
    source_format = 'cbr'
    target_format = 'folder'

    @staticmethod
    def convert(file: str) -> List[str]:
        return RARtoFOLDER.convert(file)
