# -*- coding: utf-8 -*-

from asyncio import run
from glob import glob
from itertools import chain
from os.path import abspath, basename, dirname, isfile, splitext
from typing import Any, Dict, List, Union

from backend.base.custom_exceptions import InvalidKeyValue, VolumeAlreadyAdded
from backend.base.definitions import (CONTENT_EXTENSIONS, CVFileMapping,
                                      FileConstants, FilenameData,
                                      MonitorScheme)
from backend.base.file_extraction import extract_filename_data
from backend.base.files import (delete_empty_parent_folders,
                                find_common_folder, folder_is_inside_folder,
                                list_files, propose_basefolder_change,
                                rename_file)
from backend.base.helpers import DictKeyedDict, batched, create_range
from backend.base.logging import LOGGER
from backend.implementations.comicvine import ComicVine
from backend.implementations.naming import mass_rename
from backend.implementations.root_folders import RootFolders
from backend.implementations.volumes import Library, Volume, scan_files
from backend.internals.db import commit
from backend.internals.db_models import FilesDB


def propose_library_import(
    folder_filter: Union[str, None] = None,
    limit: int = 20,
    limit_parent_folder: bool = False,
    only_english: bool = True
) -> List[dict]:
    """Get list of unimported files
    and their suggestion for a matching volume on CV.

    Args:
        folder_filter (Union[str, None], optional): Only scan the folders that
        match the given value. Can either be a folder or a glob pattern.
            Defaults to None.

        limit (int, optional): The max amount of folders to scan.
            Defaults to 20.

        limit_parent_folder (bool, optional): Base the folder limit on
        parent folder, not folder. Useful if each issue has their own sub-folder.
            Defaults to False.

        only_english (bool, optional): Only match with english releases.
            Defaults to True.

    Raises:
        InvalidKeyValue: The file filter matches to folders outside
        the root folders.

    Returns:
        List[dict]: The list of files and their matches.
    """
    LOGGER.info('Loading library import')

    # Get all files in all root folders (with filter applied if given)
    root_folders = {
        abspath(r.folder)
        for r in RootFolders().get_all()
    }

    if folder_filter:
        scan_folders = set(glob(folder_filter, recursive=True))
        for f in scan_folders:
            if not any(folder_is_inside_folder(r, f) for r in root_folders):
                raise InvalidKeyValue('folder_filter', folder_filter)
    else:
        scan_folders = root_folders.copy()

    try:
        all_files = chain.from_iterable(
            list_files(f, CONTENT_EXTENSIONS)
            for f in scan_folders
        )

    except NotADirectoryError:
        raise InvalidKeyValue('folder_filter', folder_filter)

    # Get imported files
    imported_files = {
        f["filepath"]
        for f in FilesDB.fetch()
    }

    # Filter away imported files and apply limit
    folders = set()
    image_folders = set()
    # efd to files with that efd
    unimported_files = DictKeyedDict()
    for f in all_files:
        if f in imported_files:
            continue

        d = abspath(dirname(f))
        if d in root_folders:
            # File directly in root folder is not allowed
            continue

        if f.endswith(FileConstants.IMAGE_EXTENSIONS):
            if d in image_folders:
                continue
            image_folders.add(d)
            d, f = dirname(d), d

        folders.add(
            dirname(d)
            if limit_parent_folder else
            d
        )

        if len(folders) > limit:
            break

        efd = extract_filename_data(f, prefer_folder_year=True)
        del efd['issue_number'] # type: ignore
        unimported_files.setdefault(efd, []).append(f)

    LOGGER.debug('File groupings: %s', unimported_files)

    # Find a match for the files on CV
    cv = ComicVine()
    result: List[Dict[str, Any]] = []
    uf: List[FilenameData] = list(unimported_files.keys())
    uf.sort(key=lambda f: (
        f['series'],
        create_range(f['volume_number'] or 0)[0],
        f['year'] or 0
    ))
    for batch_index, uf_batch in enumerate(batched(uf, 10)):
        group_to_cv = run(cv.filenames_to_cvs(
            uf_batch,
            only_english
        ))
        result += [
            {
                'filepath': f,
                'file_title': (
                    splitext(basename(f))[0]
                    if isfile(f) else
                    basename(f)
                ),
                'cv': search_result,
                'group_number': batch_index * 10 + group_index
            }
            for group_index, (group_data, search_result) in enumerate(group_to_cv.items())
            for f in unimported_files[group_data]
        ]

    result.sort(key=lambda e: (e['group_number'], e['file_title']))

    return result


def import_library(
    matches: List[CVFileMapping],
    rename_files: bool = False
) -> None:
    """Add volume to library and import linked files.

    Args:
        matches (List[CVFileMapping]): List of file mappings.

        rename_files (bool, optional): Trigger a rename after importing files.
            Defaults to False.
    """
    LOGGER.info('Starting library import')

    cvid_to_filepath: Dict[int, List[str]] = {}
    for m in matches:
        cvid_to_filepath.setdefault(m['id'], []).append(m['filepath'])
    LOGGER.debug(f'id_to_filepath: {cvid_to_filepath}')

    root_folders = RootFolders().get_all()
    library = Library()

    for cv_id, files in cvid_to_filepath.items():
        # Find root folder that media is in
        for root_folder in root_folders:
            if folder_is_inside_folder(root_folder.folder, files[0]):
                break
        else:
            continue

        lcf = find_common_folder(files)

        try:
            volume_id = library.add(
                comicvine_id=cv_id,
                root_folder_id=root_folder.id,
                monitor_scheme=MonitorScheme.ALL,
                volume_folder=lcf if not rename_files else None
            )
            commit()

        except VolumeAlreadyAdded:
            # The volume is already added but the file is not matched to it
            # (it isn't because otherwise it wouldn't pop up in LI).
            # That would mean that the file is actually not
            # for that volume so skip.
            continue

        if rename_files:
            # Put files in volume folder
            vf = Volume(volume_id).vd.folder
            file_changes = propose_basefolder_change(files, lcf, vf)
            for old, new in file_changes.items():
                if old != new:
                    rename_file(old, new)
                    delete_empty_parent_folders(
                        dirname(old), root_folder.folder
                    )

            new_files = list(file_changes.values())
            scan_files(volume_id)
            mass_rename(volume_id, filepath_filter=new_files)

        else:
            scan_files(volume_id, filepath_filter=files)

    return
