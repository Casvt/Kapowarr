# -*- coding: utf-8 -*-

"""
Processing/Altering individual files with permissions, ownership, file date, etc.
"""

from asyncio import run
from os.path import getsize
from typing import List, Union

from backend.base.custom_exceptions import MetadataSourceRateLimitReached
from backend.base.definitions import FileDate
from backend.base.files import (set_file_date, set_volume_folder_owner_group,
                                set_volume_folder_permissions)
from backend.base.logging import LOGGER
from backend.implementations.comicinfo import (can_embed, has_comicinfo,
                                               tag_archive)
from backend.implementations.comicvine import ComicVine
from backend.implementations.root_folders import RootFolders
from backend.internals.db import get_db
from backend.internals.db_models import FilesDB
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


def mass_set_ownership(volume_id: int) -> None:
    """Set the (chown) group owner of the volume folder, folders between the root
    folder and the volume folder, its sub-folders and its files.

    Args:
        volume_id (int): The ID of the volume for which to set the ownership.
    """
    group = Settings().sv.chown_group
    if not group:
        # Setting disabled
        return

    volume_folder, root_folder_id = get_db().execute(
        "SELECT folder, root_folder FROM volumes WHERE id = ?",
        (volume_id,)
    ).fetchone()

    set_volume_folder_owner_group(
        volume_folder,
        RootFolders()[root_folder_id],
        group
    )

    return


def embed_comicinfo(
    filepath: str,
    volume_id: int,
    force: bool = False
) -> None:
    """Embed metadata for issue as a ComicInfo.xml.

    Args:
        filepath (str): The file to tag.

        volume_id (int): The ID of the volume for which to embed the metadata.

        force (bool, optional): Whether to overwrite an existing ComicInfo.xml.
            Defaults to False.

    Raises:
        MetadataSourceRateLimitReached: The rate limit is reached.

    """
    if not can_embed(filepath):
        return

    if not force and has_comicinfo(filepath):
        return

    if not (covered := FilesDB.issues_covered(filepath)):
        return

    # Local to prevent circular import
    from backend.implementations.volumes import Volume

    volume = Volume(volume_id)
    issues = [volume.get_issue_from_number(n).get_data() for n in covered]

    credits = []
    if Settings().sv.tag_extended_metadata:
        cv = ComicVine()
        credits = [
            run(cv.fetch_issue_credits(issue.comicvine_id))
            for issue in issues
        ]

    tag_archive(filepath, volume.get_data(), issues, credits)

    get_db().execute(
        "UPDATE files SET size = ? WHERE filepath = ?;",
        (getsize(filepath), filepath)
    )
    return


def mass_tag(
    volume_id: int,
    filepath_filter: Union[List[str], None] = None,
    force: bool = False
) -> bool:
    """Embed metadata into all files of a volume.

    Args:
        volume_id (int): The ID of the volume for which to embed the metadata.

        filepath_filter (Union[List[str], None], optional): Only process files
            that are in the list.
            Defaults to None.

        force (bool, optional): Whether to overwrite an existing ComicInfo.xml.
            Defaults to False.

    Returns:
        bool: Whether all files were handled. `False` if tagging was stopped
            because the rate limit was reached.
    """
    # Local to prevent circular import
    from backend.implementations.volumes import Volume

    files = Volume(volume_id).get_all_files()

    for file in files:
        if filepath_filter is not None and file["filepath"] not in filepath_filter:
            continue
        try:
            embed_comicinfo(file["filepath"], volume_id, force=force)
        except MetadataSourceRateLimitReached:
            return False
        except Exception as e:
            LOGGER.exception(f'Failed to tag {file["filepath"]}: {e}')

    return True


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
    mass_set_ownership(volume_id)
    return
