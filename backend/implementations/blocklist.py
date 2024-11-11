# -*- coding: utf-8 -*-

from time import time
from typing import List, Union

from backend.base.custom_exceptions import BlocklistEntryNotFound
from backend.base.definitions import (BlocklistEntry, BlocklistReason,
                                      BlocklistReasonID, DownloadSource)
from backend.base.logging import LOGGER
from backend.internals.db import get_db


# region Get
def get_blocklist(offset: int = 0) -> List[BlocklistEntry]:
    """Get the blocklist entries in blocks of 50.

    Args:
        offset (int, optional): The offset of the list.
            The higher the number, the deeper into the list you go.

            Defaults to 0.

    Returns:
        List[BlocklistEntry]: A list of the current entries in the blocklist.
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

    result = [
        BlocklistEntry(**{
            **entry,
            "reason": BlocklistReason[
                BlocklistReasonID(entry["reason"]).name
            ]
        })
        for entry in entries
    ]

    return result


def get_blocklist_entry(id: int) -> BlocklistEntry:
    """Get info about a blocklist entry.

    Args:
        id (int): The id of the blocklist entry.

    Raises:
        BlocklistEntryNotFound: The id doesn't map to any blocklist entry.

    Returns:
        BlocklistEntry: The info of the blocklist entry.
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

    return BlocklistEntry(**{
        **entry,
        "reason": BlocklistReason[
            BlocklistReasonID(entry["reason"]).name
        ]
    })


# region Contains and Add
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
) -> BlocklistEntry:
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
        BlocklistEntry: Info about the blocklist entry.
    """
    # Select link to blocklist
    blocked_link = download_link or web_link
    if not blocked_link:
        raise ValueError("No page link or download link supplied")

    # Stop if it's already added
    id = blocklist_contains(blocked_link)
    if id:
        return get_blocklist_entry(id)

    # Add to database
    LOGGER.info(
        f'Adding {blocked_link} to blocklist with reason "{reason.value}"'
    )

    reason_id = BlocklistReasonID[reason.name].value
    source_value = source.value if source is not None else None
    id = get_db().execute("""
        INSERT INTO blocklist(
            volume_id, issue_id,
            web_link, web_title, web_sub_title,
            download_link, source,
            reason, added_at
        )
        VALUES (
            :volume_id, :issue_id,
            :web_link, :web_title, :web_sub_title,
            :download_link, :source,
            :reason, :added_at
        );
        """,
        {
            "volume_id": volume_id,
            "issue_id": issue_id,
            "web_link": web_link,
            "web_title": web_title,
            "web_sub_title": web_sub_title,
            "download_link": download_link,
            "source": source_value,
            "reason": reason_id,
            "added_at": round(time())
        }
    ).lastrowid

    return get_blocklist_entry(id)


# region Delete
def delete_blocklist() -> None:
    """Delete all blocklist entries."""
    LOGGER.info('Deleting blocklist')
    get_db().execute(
        "DELETE FROM blocklist;"
    )
    return


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

    if not entry_found:
        raise BlocklistEntryNotFound

    return
