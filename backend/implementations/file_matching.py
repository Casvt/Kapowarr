# -*- coding: utf-8 -*-

"""
The matching of files to issues in a volume
"""

from collections import Counter
from os.path import isdir
from typing import Dict, List, Union

from backend.base.definitions import (FileConstants, GeneralFileType,
                                      SpecialVersion)
from backend.base.file_extraction import extract_filename_data
from backend.base.files import (create_folder, delete_empty_child_folders,
                                delete_empty_parent_folders, list_files)
from backend.base.helpers import (extract_year_from_date,
                                  filtered_iter, force_range)
from backend.base.logging import LOGGER
from backend.implementations.matching import file_importing_filter
from backend.implementations.root_folders import RootFolders
from backend.internals.db import commit, get_db
from backend.internals.db_models import FilesDB
from backend.internals.server import DownloadedStatusEvent, WebSocket
from backend.internals.settings import Settings


def scan_files(
    volume_id: int,
    filepath_filter: List[str] = [],
    del_unmatched_files: bool = True,
    update_websocket: bool = False
) -> None:
    """Scan inside the volume folder for files and map them to issues.

    Args:
        volume_id (int): The ID of the volume to scan for.

        filepath_filter (List[str], optional): Only scan specific files.
            Intended for adding files to a volume only.
            Defaults to [].

        del_unmatched_files (bool, optional): Delete file entries in the DB
            that aren't linked to anything anymore.
            Defaults to True.

        update_websocket (bool, optional): Send websocket messages on changes
            about the download status of the issues.
            Defaults to False.
    """
    from backend.implementations.volumes import Volume

    LOGGER.debug(f'Scanning for files for {volume_id}')

    settings = Settings().get_settings()
    volume = Volume(volume_id)
    volume_data = volume.get_data()

    if not isdir(volume_data.folder):
        if settings.create_empty_volume_folders:
            create_folder(volume_data.folder)
        else:
            return

    volume_issues = volume.get_issues(_skip_files=True)
    volume_issues.sort(key=lambda i: i.calculated_issue_number)
    number_to_year: Dict[float, Union[int, None]] = {
        i.calculated_issue_number: extract_year_from_date(i.date)
        for i in volume_issues
    }
    current_issue_files = {
        f['filepath']: f['id']
        for f in volume.get_all_files()
    }

    new_issue_bindings: Dict[int, int] = {}
    new_general_bindings: Dict[int, str] = {}
    folder_contents = list_files(
        folder=volume_data.folder,
        ext=FileConstants.SCANNABLE_EXTENSIONS
    )
    for file in filtered_iter(folder_contents, set(filepath_filter)):
        file_data = extract_filename_data(file)

        # Check if file matches volume
        if not file_importing_filter(
            file_data,
            volume_data,
            volume_issues,
            number_to_year
        ):
            continue

        if (
            file_data['special_version'] == SpecialVersion.COVER
            and file_data["issue_number"] is None
        ):
            # Volume cover file
            if file not in current_issue_files:
                current_issue_files[file] = FilesDB.add_file(file)

            new_general_bindings[current_issue_files[file]] = (
                GeneralFileType.COVER.value
            )

        elif (
            file_data['special_version'] == SpecialVersion.METADATA
            and file_data["issue_number"] is None
        ):
            # Volume metadata file
            if file not in current_issue_files:
                current_issue_files[file] = FilesDB.add_file(file)

            new_general_bindings[current_issue_files[file]] = (
                GeneralFileType.METADATA.value
            )

        elif (
            volume_data.special_version not in (
                SpecialVersion.VOLUME_AS_ISSUE,
                SpecialVersion.NORMAL
            )
            and file_data['special_version']
        ):
            # Special Version
            if file not in current_issue_files:
                current_issue_files[file] = FilesDB.add_file(file)

            new_issue_bindings[current_issue_files[file]] = volume_issues[0].id

        elif (
            file_data['issue_number'] is not None
            or volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
        ):
            # Normal issue
            issue_range = file_data["issue_number"]
            if (
                volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
                and file_data["issue_number"] is None
            ):
                issue_range = file_data['volume_number']

            if issue_range is None:
                continue
            if not isinstance(issue_range, tuple):
                issue_range = force_range(issue_range)

            matching_issues = [
                issue.id
                for issue in volume_issues
                if (
                    issue_range[0]
                    <= issue.calculated_issue_number
                    <= issue_range[1]
                )
            ]

            if matching_issues:
                if file not in current_issue_files:
                    current_issue_files[file] = FilesDB.add_file(file)

                for issue in matching_issues:
                    new_issue_bindings[current_issue_files[file]] = issue

    cursor = get_db()

    # Determine old and new bindings, and which issues change in
    # their marking of being downloaded because of the new bindings
    current_bindings: Dict[int, int] = dict(cursor.execute("""
        SELECT if.file_id, if.issue_id
        FROM issues_files if
        INNER JOIN issues i
        ON if.issue_id = i.id
        WHERE i.volume_id = ?;
        """,
        (volume_id,)
    ))
    delete_bindings = {
        bf: bi
        for bf, bi in current_bindings.items()
        if new_issue_bindings.get(bf) != bi
    }
    add_bindings = {
        bf: bi
        for bf, bi in new_issue_bindings.items()
        if current_bindings.get(bf) != bi
    }

    issue_binding_count = Counter(current_bindings.values())

    new_binding_count = Counter(add_bindings.values())
    issue_binding_count.update(new_binding_count)
    newly_downloaded_issues = list(new_binding_count)

    delete_binding_count = Counter(delete_bindings.values())
    issue_binding_count.subtract(delete_binding_count)
    deleted_downloaded_issues = [
        k
        for k, v in issue_binding_count.items()
        if not v
    ]

    # Delete bindings that aren't in new bindings
    if not filepath_filter:
        cursor.executemany(
            "DELETE FROM issues_files WHERE file_id = ? AND issue_id = ?;",
            delete_bindings.items()
        )

        if settings.unmonitor_deleted_issues:
            cursor.executemany(
                "UPDATE issues SET monitored = 0 WHERE id = ?;",
                ((issue_id,) for issue_id in deleted_downloaded_issues)
            )

    # Add bindings that aren't in current bindings
    cursor.executemany(
        "INSERT INTO issues_files(file_id, issue_id) VALUES (?, ?);",
        add_bindings.items()
    )

    # Delete bindings for general files that aren't in new bindings
    if not filepath_filter:
        current_general_bindings = {
            gf['id']: gf['file_type']
            for gf in volume.get_general_files()
        }
        delete_general_bindings = (
            (b,)
            for b in current_general_bindings
            if b not in new_general_bindings
        )
        cursor.executemany(
            "DELETE FROM volume_files WHERE file_id = ?;",
            delete_general_bindings
        )

    # Add bindings for general files that aren't in current bindings
    cursor.executemany("""
        INSERT INTO volume_files(
            file_id, volume_id, file_type
        ) VALUES (
            ?, ?, ?
        )
        ON CONFLICT(file_id) DO
        UPDATE SET
            file_type = ?;
        """,
        (
            (file_id, volume_id, file_type, file_type)
            for file_id, file_type in new_general_bindings.items()
        )
    )

    # Remove files from the database that aren't matched to anything anymore
    if del_unmatched_files:
        FilesDB.delete_unmatched_files()

    commit()

    if update_websocket:
        if not filepath_filter and (
            deleted_downloaded_issues or newly_downloaded_issues
        ):
            WebSocket().emit(DownloadedStatusEvent(
                volume_id,
                not_downloaded_issues=deleted_downloaded_issues,
                downloaded_issues=newly_downloaded_issues
            ))

        elif filepath_filter and newly_downloaded_issues:
            WebSocket().emit(DownloadedStatusEvent(
                volume_id,
                downloaded_issues=newly_downloaded_issues
            ))

    if settings.delete_empty_folders:
        delete_empty_child_folders(volume_data.folder, skip_hidden_folders=True)
        if (
            not list_files(volume_data.folder)
            and not settings.create_empty_volume_folders
        ):
            delete_empty_parent_folders(
                volume_data.folder,
                RootFolders()[volume_data.root_folder]
            )

    return
