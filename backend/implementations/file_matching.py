# -*- coding: utf-8 -*-

"""
The matching of files to issues in a volume
"""

from collections import Counter
from os.path import basename, isdir
from typing import Dict, List, Set, Tuple, Union

from backend.base.definitions import (FileConstants, FileMatch,
                                      GeneralFileType, SpecialVersion)
from backend.base.file_extraction import (extract_filename_data,
                                          refine_special_version)
from backend.base.files import (create_folder, delete_empty_child_folders,
                                delete_empty_parent_folders,
                                folder_is_inside_folder, list_files)
from backend.base.helpers import (extract_year_from_date,
                                  filtered_iter, force_range)
from backend.base.logging import LOGGER
from backend.implementations.matching import file_importing_filter
from backend.implementations.root_folders import RootFolders
from backend.internals.db import commit, get_db
from backend.internals.db_models import FilesDB
from backend.internals.server import DownloadedStatusEvent, WebSocket
from backend.internals.settings import Settings


# region Automatic Match
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

    cursor = get_db()
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

    # Skip processing manually matched files, but do note that they are found
    manually_matched_files: Dict[str, int] = dict(cursor.execute(
        """
        SELECT DISTINCT f.filepath, f.id
        FROM files f
        INNER JOIN issues_files if
        INNER JOIN issues i
        ON f.id = if.file_id
            AND if.issue_id = i.id
        WHERE i.volume_id = ?
            AND if.forced = ?
        """,
        (volume_id, True)
    ))
    manually_matched_files_found: Set[int] = set()
    manually_matched_general_files: Dict[str, int] = dict(cursor.execute(
        """
        SELECT DISTINCT f.filepath, f.id
        FROM files f
        INNER JOIN volume_files vf
        ON f.id = vf.file_id
        WHERE vf.volume_id = ?
            AND vf.forced = ?
        """,
        (volume_id, True)
    ))
    manually_matched_general_files_found: Set[int] = set()

    new_issue_bindings: Set[Tuple[int, int]] = set()
    new_general_bindings: Dict[int, str] = {}
    folder_contents = list_files(
        folder=volume_data.folder,
        ext=FileConstants.SCANNABLE_EXTENSIONS
    )
    for file in filtered_iter(folder_contents, set(filepath_filter)):
        if file in manually_matched_files:
            # File already manually matched to issue(s)
            manually_matched_files_found.add(
                manually_matched_files.pop(file)
            )
            continue

        elif file in manually_matched_general_files:
            # File already manually matched as general file of volume
            manually_matched_general_files_found.add(
                manually_matched_general_files.pop(file)
            )
            continue

        file_data = extract_filename_data(file)

        # Check if file matches volume
        if not file_importing_filter(
            file_data,
            volume_data,
            volume_issues,
            number_to_year
        ):
            continue

        file_data = refine_special_version(volume_data, file_data)

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

            new_issue_bindings.add(
                (current_issue_files[file], volume_issues[0].id)
            )

        elif file_data["issue_number"] is not None:
            # Normal issue
            if isinstance(file_data["issue_number"], tuple):
                n_start, n_end = file_data["issue_number"]
            else:
                n_start, n_end = force_range(file_data["issue_number"])

            matching_issues = [
                issue.id
                for issue in volume_issues
                if n_start <= issue.calculated_issue_number <= n_end
            ]

            if matching_issues:
                if file not in current_issue_files:
                    current_issue_files[file] = FilesDB.add_file(file)

                for issue in matching_issues:
                    new_issue_bindings.add(
                        (current_issue_files[file], issue)
                    )

    # Determine old and new bindings, and which issues change in
    # their marking of being downloaded because of the new bindings
    manually_matched_files_missing = set(manually_matched_files.values())
    current_bindings: Set[Tuple[int, int]] = set(map(tuple, cursor.execute("""
        SELECT if.file_id, if.issue_id
        FROM issues_files if
        INNER JOIN issues i
        ON if.issue_id = i.id
        WHERE i.volume_id = ?;
        """,
        (volume_id,)
    )))
    delete_bindings = {
        (file_id, issue_id)
        for file_id, issue_id in current_bindings
        if (
            (file_id, issue_id) not in new_issue_bindings
            and file_id not in manually_matched_files_found

            or file_id in manually_matched_files_missing
        )
    }
    add_bindings = {
        (file_id, issue_id)
        for file_id, issue_id in new_issue_bindings
        if (file_id, issue_id) not in current_bindings
    }

    issue_binding_count = Counter((b[1] for b in current_bindings))

    new_binding_count = Counter((b[1] for b in add_bindings))
    issue_binding_count.update(new_binding_count)
    newly_downloaded_issues = list(new_binding_count)

    delete_binding_count = Counter((b[1] for b in delete_bindings))
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
            delete_bindings
        )

        if settings.unmonitor_deleted_issues:
            cursor.executemany(
                "UPDATE issues SET monitored = 0 WHERE id = ?;",
                ((issue_id,) for issue_id in deleted_downloaded_issues)
            )

    # Add bindings that aren't in current bindings
    cursor.executemany(
        "INSERT INTO issues_files(file_id, issue_id) VALUES (?, ?);",
        add_bindings
    )

    # Delete bindings for general files that aren't in new bindings
    if not filepath_filter:
        manually_matched_general_files_missing = set(
            manually_matched_general_files.values()
        )
        current_general_bindings = {
            gf['id']: gf['file_type']
            for gf in volume.get_general_files()
        }
        delete_general_bindings = (
            (b,)
            for b in current_general_bindings
            if (
                b not in new_general_bindings
                and b not in manually_matched_general_files_found

                or b in manually_matched_general_files_missing
            )
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


# region Manual Match
def get_file_matching(volume_id: int) -> List[FileMatch]:
    """Get the matchings of all files in the volume folder. Either they match to
    nothing, one or more issues or it's a general file.

    Args:
        volume_id (int): The ID of the volume.

    Returns:
        List[FileMatch]: A list of all files in the volume folder and their match.
    """
    cursor = get_db()

    # Add a files in folder to list
    volume_folder: str = cursor.execute(
        "SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
        (volume_id,)
    ).fetchone()[0]

    folder_files = list_files(volume_folder, FileConstants.SCANNABLE_EXTENSIONS)
    folder_files.sort()
    current_matches: Dict[str, FileMatch] = {
        filepath: {
            "filepath": filepath,
            "issue_ids": [],
            "general_file": False,
            "forced_match": False
        }
        for filepath in folder_files
    }

    # Update file entries with their issue matches
    cursor.execute("""
        SELECT f.filepath, if.issue_id, if.forced
        FROM files f
        INNER JOIN issues_files if
        INNER JOIN issues i
        ON f.id = if.file_id
            AND if.issue_id = i.id
        WHERE volume_id = ?
        ORDER BY if.issue_id;
        """,
        (volume_id,)
    )

    for filepath, issue_id, forced in cursor:
        try:
            file_match = current_matches[filepath]
        except KeyError:
            continue
        file_match["issue_ids"].append(issue_id)
        file_match["forced_match"] = forced

    # Update file entries with their general file matches
    cursor.execute("""
        SELECT f.filepath, vf.forced
        FROM files f
        INNER JOIN volume_files vf
        ON f.id = vf.file_id
        WHERE vf.volume_id = ?;
        """,
        (volume_id,)
    )

    for filepath, forced in cursor:
        try:
            general_match = current_matches[filepath]
        except KeyError:
            continue
        general_match["general_file"] = True
        general_match["forced_match"] = forced

    return list(current_matches.values())


def set_file_matching(volume_id: int, matches: List[FileMatch]) -> None:
    """Set the matchings of files in a volume's folder so that they match to one
    or more issues, become a general file or are allowed to match automatically.
    For a FileMatch entry, set `forced_match` to `True` and supply the IDs of
    the issues that it should match to or set `general_file` to `True`. If it
    should be set to automatically match (like a normal file), set `forced_match`
    to `False`. Leave out entries to not change their matching. Afterwards, a
    file scan is automatically done (in case a file that was previously force
    matched can now be automatically matched).

    Args:
        volume_id (int): The ID of the volume.
        matches (List[FileMatch]): A list of files and their desired matching.
    """
    cursor = get_db()
    volume_folder: str = cursor.execute(
        "SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
        (volume_id,)
    ).fetchone()[0]

    for file_match in matches:
        if not folder_is_inside_folder(volume_folder, file_match['filepath']):
            continue

        # Add file to database if needed; get file ID
        file_id = FilesDB.add_file(file_match["filepath"])

        if not file_match["forced_match"]:
            cursor.execute(
                "UPDATE volume_files SET forced = ? WHERE file_id = ?;",
                (False, file_id,)
            )
            cursor.execute(
                "UPDATE issues_files SET forced = ? WHERE file_id = ?;",
                (False, file_id,)
            )

        else:
            if not file_match["general_file"]:
                # Remove potential general match
                cursor.execute(
                    "DELETE FROM volume_files WHERE file_id = ?;",
                    (file_id,)
                )

            # Remove any issue matches that aren't in the list
            cursor.execute(f"""
                DELETE FROM issues_files
                WHERE file_id = ?
                    AND issue_id NOT IN ({','.join(['?'] * len(file_match["issue_ids"]))})
                """,
                (file_id, *file_match["issue_ids"])
            )

            # Insert or update match in appropriate table
            if file_match["general_file"]:
                is_metadata_file = (
                    basename(file_match["filepath"].lower())
                    in FileConstants.METADATA_FILES
                )
                if is_metadata_file:
                    file_type = GeneralFileType.METADATA.value
                else:
                    file_type = GeneralFileType.COVER.value

                cursor.execute("""
                    INSERT INTO volume_files(
                        file_id, volume_id, file_type, forced
                    ) VALUES (
                        :file_id, :volume_id, :file_type, :forced
                    )
                    ON CONFLICT(file_id) DO
                    UPDATE SET forced = :forced;
                    """,
                    {
                        "file_id": file_id,
                        "volume_id": volume_id,
                        "file_type": file_type,
                        "forced": True
                    }
                )

            else:
                cursor.executemany("""
                    INSERT INTO issues_files(file_id, issue_id, forced)
                        VALUES (:file_id, :issue_id, :forced)
                    ON CONFLICT(file_id, issue_id) DO
                    UPDATE SET forced = :forced;
                    """,
                    (
                        {
                            "file_id": file_id,
                            "issue_id": issue_id,
                            "forced": True
                        }
                        for issue_id in file_match["issue_ids"]
                    )
                )

    scan_files(volume_id, update_websocket=True)

    return
