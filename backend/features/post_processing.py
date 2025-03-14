# -*- coding: utf-8 -*-

"""
The post-download processing (a.k.a. post-processing or PP) of downloads.
"""

from __future__ import annotations

from os.path import basename, exists, join, splitext
from time import time
from typing import TYPE_CHECKING

from backend.base.definitions import SCANNABLE_EXTENSIONS, BlocklistReason
from backend.base.files import copy_directory, delete_file_folder, rename_file
from backend.base.logging import LOGGER
from backend.implementations.blocklist import add_to_blocklist
from backend.implementations.conversion import mass_convert
from backend.implementations.converters import extract_files_from_folder
from backend.implementations.download_clients import TorrentDownload
from backend.implementations.naming import mass_rename
from backend.implementations.volumes import Volume, scan_files
from backend.internals.db import commit, get_db
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from backend.base.definitions import Download


# region General
def reset_file_link(download: TorrentDownload) -> None:
    "Set download.files back to original folder from the copied folder"
    download.files = download._original_files
    return


# region Database
def remove_from_queue(download: Download) -> None:
    "Delete the download from the queue in the database"
    get_db().execute(
        "DELETE FROM download_queue WHERE id = ?",
        (download.id,)
    )
    return


def add_to_history(download: Download) -> None:
    "Add the download to history in the database"
    get_db().execute(
        """
        INSERT INTO download_history(
            web_link, web_title, web_sub_title,
            file_title,
            volume_id, issue_id,
            source, downloaded_at
        ) VALUES (
            :web_link, :web_title, :web_sub_title,
            :file_title,
            :volume_id, :issue_id,
            :source, :downloaded_at
        );
        """,
        {
            'web_link': download.web_link,
            'web_title': download.web_title,
            'web_sub_title': download.web_sub_title,
            'file_title': download.title,
            'volume_id': download.volume_id,
            'issue_id': download.issue_id,
            'source': download.source_type.value,
            'downloaded_at': round(time())
        }
    )
    return


def add_file_to_database(download: Download) -> None:
    "Register files in database and match to a volume/issue"
    scan_files(download.volume_id, filepath_filter=download.files)
    return


# region Blocklist
def add_dl_to_blocklist(download: Download) -> None:
    "Add the download to the blocklist in the database"
    add_to_blocklist(
        download.web_link,
        download.web_title,
        download.web_sub_title,
        download.download_link,
        download.source_type,
        download.volume_id,
        download.issue_id,
        BlocklistReason.LINK_BROKEN
    )
    return


# region Files
def move_to_dest(download: Download) -> None:
    "Move file/fold from download folder to final destination"
    if not exists(download.files[0]):
        return

    folder = Volume(download.volume_id).vd.folder
    extension = splitext(download.files[0])[1].lower()
    if extension not in SCANNABLE_EXTENSIONS:
        extension = ''

    file_dest = join(
        folder,
        download.filename_body + extension
    )
    LOGGER.debug(
        f'Moving download to final destination: {download}, Dest: {file_dest}'
    )

    # If it takes very long to delete/move the file/folder (because of it's size),
    # the DB is left locked for a long period leading to timeouts.
    commit()

    if exists(file_dest):
        LOGGER.warning(
            f'The file/folder {file_dest} already exists; replacing with downloaded file'
        )
        delete_file_folder(file_dest)

    rename_file(download.files[0], file_dest)
    download.files = [file_dest]
    return


def move_torrent_to_dest(download: TorrentDownload) -> None:
    """
    Move folder downloaded using torrent from download folder to
    final destination, extract files, scan them, rename them.
    """
    if not exists(download.files[0]):
        return

    move_to_dest(download)

    download.files = extract_files_from_folder(
        download.files[0],
        download.volume_id
    )

    if not download.files:
        return

    scan_files(
        download.volume_id,
        filepath_filter=download.files
    )

    rename_files = Settings().sv.rename_downloaded_files
    if rename_files:
        download.files += mass_rename(
            download.volume_id,
            filepath_filter=download.files
        )

    return


def copy_file_torrent(download: TorrentDownload) -> None:
    """
    Copy downloaded files to dest. Change download.file to copy.
    Change back using `PPA.reset_file_link()`.
    """
    download._original_files = download.files
    if not exists(download.files[0]):
        return

    folder = Volume(download.volume_id).vd.folder
    file_dest = join(folder, basename(download.files[0]))
    LOGGER.debug(
        f'Copying download to final destination: {download}, Dest: {file_dest}'
    )

    # If it takes very long to delete/copy the folder (because of it's size),
    # the DB is left locked for a long period leading to timeouts.
    commit()

    if exists(file_dest):
        LOGGER.warning(
            f'The file/folder {file_dest} already exists; replacing with downloaded file'
        )
        delete_file_folder(file_dest)

    copy_directory(download.files[0], file_dest)

    download.files = extract_files_from_folder(
        file_dest,
        download.volume_id
    )

    if not download.files:
        return

    scan_files(
        download.volume_id,
        filepath_filter=download.files
    )

    rename_files = Settings().sv.rename_downloaded_files
    if rename_files:
        download.files += mass_rename(
            download.volume_id,
            filepath_filter=download.files
        )

    return


def delete_file(download: Download) -> None:
    "Delete file from download folder"
    for f in download.files:
        delete_file_folder(f)
    return


# region Extras
def convert_file(download: Download) -> None:
    "Convert a file into a different format based on settings"
    if not Settings().sv.convert:
        return

    download.files += mass_convert(
        download.volume_id,
        download.issue_id,
        filepath_filter=download.files
    )
    return


class PostProcesser:
    actions_success = [
        remove_from_queue,
        add_to_history,
        move_to_dest,
        add_file_to_database,
        convert_file,
        add_file_to_database
    ]

    actions_seeding = []

    actions_canceled = [
        delete_file,
        remove_from_queue
    ]

    actions_shutdown = [
        delete_file
    ]

    actions_failed = [
        remove_from_queue,
        add_to_history,
        delete_file
    ]

    actions_perm_failed = [
        remove_from_queue,
        add_to_history,
        add_dl_to_blocklist,
        delete_file
    ]

    @staticmethod
    def _run_actions(actions: list, download) -> None:
        for action in actions:
            action(download)
        return

    @classmethod
    def success(cls, download) -> None:
        LOGGER.info(f'Postprocessing of successful download: {download.id}')
        cls._run_actions(cls.actions_success, download)
        return

    @classmethod
    def seeding(cls, download) -> None:
        LOGGER.info(f'Postprocessing of seeding download: {download.id}')
        cls._run_actions(cls.actions_seeding, download)
        return

    @classmethod
    def canceled(cls, download) -> None:
        LOGGER.info(f'Postprocessing of canceled download: {download.id}')
        cls._run_actions(cls.actions_canceled, download)
        return

    @classmethod
    def shutdown(cls, download) -> None:
        LOGGER.info(f'Postprocessing of shut down download: {download.id}')
        cls._run_actions(cls.actions_shutdown, download)
        return

    @classmethod
    def failed(cls, download) -> None:
        LOGGER.info(f'Postprocessing of failed download: {download.id}')
        cls._run_actions(cls.actions_failed, download)
        return

    @classmethod
    def perm_failed(cls, download) -> None:
        LOGGER.info(
            f'Postprocessing of permanently failed download: {download.id}'
        )
        cls._run_actions(cls.actions_perm_failed, download)
        return


class PostProcesserTorrentsComplete(PostProcesser):
    actions_success = [
        remove_from_queue,
        add_to_history,
        move_torrent_to_dest,
        convert_file,
        add_file_to_database
    ]


class PostProcesserTorrentsCopy(PostProcesser):
    actions_success = [
        remove_from_queue,
        delete_file
    ]

    actions_seeding = [
        add_to_history,
        copy_file_torrent,
        convert_file,
        add_file_to_database,
        reset_file_link
    ]
