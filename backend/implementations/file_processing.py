# -*- coding: utf-8 -*-

"""
Processing/Altering individual files with permissions, ownership, file date, etc.
"""

from typing import List, Union

from backend.base.definitions import FileDate
from backend.base.files import set_file_date, set_volume_folder_permissions
from backend.implementations.root_folders import RootFolders
from backend.internals.db import get_db
from backend.internals.settings import Settings


def mass_set_file_date(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None
) -> None:
    """Set the date of the issue files to the release date of the issue.

    Args:
        volume_id (int): The ID of the volume for which to set the file dates.

        issue_id (Union[int, None], optional): The ID of the issue for which
            to set the file dates, instead of all volume files.
            Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only process files
            that are in the list.
            Defaults to None.
    """
    if Settings().sv.change_file_date == FileDate.NONE:
        # Setting disabled
        return

    issue_filter = ""
    filepath_sql_filter = ""
    if issue_id:
        issue_filter = "AND i.id = :issue_id"
    if filepath_filter:
        filepath_list = "'" + "','".join(filepath_filter) + "'"
        filepath_sql_filter = f"AND f.filepath IN ({filepath_list})"

    cursor = get_db()
    cursor.execute(f"""
        SELECT f.filepath, i.date
        FROM files f
        INNER JOIN issues_files if
        INNER JOIN issues i
        ON f.id = if.file_id
            AND if.issue_id = i.id
        WHERE i.volume_id = :volume_id
            {issue_filter}
            {filepath_sql_filter}
            AND i.date IS NOT NULL
        """,
        {
            "volume_id": volume_id,
            "issue_id": issue_id or -1
        }
    )

    for filepath, date in cursor:
        set_file_date(filepath, date)

    return


def mass_set_permissions(volume_id: int) -> None:
    """Set the (chmod) permissions of a volume folder, folders between the root
    folder and the volume folder, its sub-folders and its files. The folders are
    set according to the setting value. The files are set similarly but without
    the execution bit.

    Args:
        volume_id (int): The ID of the volume for which to set the permissions.
    """
    permissions = Settings().sv.chmod_folder
    if not permissions:
        # Setting disabled
        return

    volume_folder, root_folder_id = get_db().execute(
        "SELECT folder, root_folder FROM volumes WHERE id = ?",
        (volume_id,)
    ).fetchone()

    set_volume_folder_permissions(
        volume_folder,
        RootFolders()[root_folder_id],
        permissions
    )

    return


def mass_process_files(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None
) -> None:
    """Process individual files (and folders), mostly by setting properties.
    Sets things like file date, permissions and ownership, based on the settings.

    Args:
        volume_id (int): The ID of the volume for which the files should be
            processed.

        issue_id (Union[int, None], optional): The ID of the issue for which the
            files should specifically be processed. Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only process files
            that are in the list.
            Defaults to None.
    """
    mass_set_file_date(volume_id, issue_id, filepath_filter)
    mass_set_permissions(volume_id)
    return
