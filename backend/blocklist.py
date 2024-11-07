# -*- coding: utf-8 -*-

from time import time
from typing import Any, Dict, List, Union

from backend.custom_exceptions import BlocklistEntryNotFound
from backend.db import get_db
from backend.definitions import (BlocklistReason,
                                 BlocklistReasonID, DownloadSource)
from backend.logging import LOGGER


def get_blocklist(offset: int = 0) -> List[Dict[str, Any]]:
    """Get the blocklist entries in blocks of 50.

    Args:
        offset (int, optional): The offset of the list.
            The higher the number, the deeper into the list you go.

            Defaults to 0.

    Returns:
        List[Dict[str, Any]]: A list of dicts where each dict is a blocklist
        entry.
    """
    entries = get_db().execute("""
        SELECT
            id, volume_id, issue_id,
            web_link, web_title, web_sub_title,
            download_link, source,
            reason, added_at
        FROM blocklist
        ORDER BY id DESC
        LIMIT 50
        OFFSET ?;
        """,
        (offset * 50,)
    ).fetchalldict()

    for entry in entries:
        entry.update({
            'reason': BlocklistReason[
                BlocklistReasonID(entry['reason']).name
            ].value
        })

    return entries


def delete_blocklist() -> None:
    """Delete all blocklist entries
    """
    LOGGER.info('Deleting blocklist')
    get_db().execute(
        "DELETE FROM blocklist;"
    )
    return


def get_blocklist_entry(id: int) -> Dict[str, Any]:
    """Get info about a blocklist entry.

    Args:
        id (int): The id of the blocklist entry.

    Raises:
        BlocklistEntryNotFound: The id doesn't map to any blocklist entry.

    Returns:
        Dict[str, Any]: The info about the blocklist entry, similar to the dicts
        in the output of `blocklist.get_blocklist()`
    """
    entry = get_db().execute("""
        SELECT
            id, volume_id, issue_id,
            web_link, web_title, web_sub_title,
            download_link, source,
            reason, added_at
        FROM blocklist
        WHERE id = ?
        LIMIT 1;
        """,
        (id,)
    ).fetchonedict()

    if not entry:
        raise BlocklistEntryNotFound

    entry['reason'] = BlocklistReason[
        BlocklistReasonID(entry['reason']).name
    ].value
    return entry


def delete_blocklist_entry(id: int) -> None:
    """Delete a blocklist entry.

    Args:
        id (int): The id of the blocklist entry.

    Raises:
        BlocklistEntryNotFound: The id doesn't map to any blocklist entry.
    """
    LOGGER.debug(f'Deleting blocklist entry {id}')
    entry_found = get_db().execute(
        "DELETE FROM blocklist WHERE id = ?",
        (id,)
    ).rowcount

    if entry_found:
        return
    raise BlocklistEntryNotFound


def blocklist_contains(link: str) -> Union[int, None]:
    """Check if a link is in the blocklist.

    Args:
        link (str): The link to check for.

    Returns:
        Union[int, None]: The ID of the blocklist entry, if found. Otherwise
        `None`.
    """
    result = get_db().execute("""
        SELECT id
        FROM blocklist
        WHERE download_link = ?
            OR (web_link = ? AND download_link IS NULL)
        LIMIT 1;
        """,
        (link, link)
    ).exists()
    return result


def add_to_blocklist(
    web_link: Union[str, None],
    web_title: Union[str, None],

    web_sub_title: Union[str, None],
    download_link: Union[str, None],
    source: Union[DownloadSource, None],

    volume_id: int,
    issue_id: Union[int, None],

    reason: BlocklistReason
) -> Dict[str, Any]:
    """Add a link to the blocklist.

    Args:
        web_link (Union[str, None]): The link to the GC page.

        web_title (Union[str, None]): The title of the GC release.

        web_sub_title (Union[str, None]): The name of the download group on the
        GC page.

        download_link (str): The link to block. Give `None` to block the whole
        GC page (`web_link`).

        source (Union[DownloadSource, None]): The source of the download.

        volume_id (int): The ID of the volume for which this link is
        blocklisted.

        issue_id (Union[int, None]): The ID of the issue for which this link is
        blocklisted, if the link is for a specific issue.

        reason (BlocklistReasons): The reason why the link is blocklisted.
            See `backend.enums.BlocklistReason`.

    Returns:
        Dict[str, Any]: Info about the blocklist entry.
    """
    blocked_link = download_link if download_link is not None else web_link
    if not blocked_link:
        raise ValueError("No page link or download link supplied")

    id = blocklist_contains(blocked_link)
    if id:
        return get_blocklist_entry(id)

    LOGGER.info(
        f'Adding {blocked_link} to blocklist with reason "{reason.value}"'
    )

    reason_id = BlocklistReasonID[reason.name].value
    id = get_db().execute("""
        INSERT INTO blocklist(
            volume_id, issue_id,
            web_link, web_title, web_sub_title,
            download_link, source,
            reason, added_at
        )
        VALUES (
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?
        );
        """,
        (
            volume_id, issue_id,
            web_link, web_title, web_sub_title,
            download_link, source.value if source is not None else None,
            reason_id, round(time())
        )
    ).lastrowid

    return get_blocklist_entry(id)
