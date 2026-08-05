# -*- coding: utf-8 -*-

from __future__ import annotations

from os.path import basename, exists, isfile, join, splitext
from time import time
from typing import TYPE_CHECKING, Dict

from backend.base.definitions import (BlocklistReason,
                                      DownloadState, FileConstants)
from backend.base.files import (copy_directory, delete_file_folder,
                                rename_file, set_detected_extension)
from backend.base.logging import LOGGER
from backend.implementations.blocklist import add_to_blocklist
from backend.implementations.conversion import mass_convert
from backend.implementations.converters import extract_files_from_folder
from backend.implementations.file_matching import scan_files
from backend.implementations.file_processing import mass_process_files
from backend.implementations.naming import mass_rename
from backend.implementations.volumes import Volume
from backend.internals.db import commit, get_db
from backend.internals.db_models import FilesDB
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from backend.base.definitions import Download


class PostProcessingContext:
    def __init__(self, download: Download) -> None:
        self.download = download
        self.original_files = download.files
        return

    # region Ctx Database
    def remove_from_queue(self) -> None:
        "Delete the download from the queue in the database"
        get_db().execute(
            "DELETE FROM download_queue WHERE id = ?",
            (self.download.id,)
        ).connection.commit()
        return

    def add_to_history(self) -> None:
        "Add the download to history in the database"
        get_db().execute(
            """
            INSERT INTO download_history(
                web_link, web_title, web_sub_title,
                file_title,
                volume_id, issue_id,
                source, downloaded_at, success
            ) VALUES (
                :web_link, :web_title, :web_sub_title,
                :file_title,
                :volume_id, :issue_id,
                :source, :downloaded_at, :success
            );
            """,
            {
                'web_link': self.download.web_link,
                'web_title': self.download.web_title,
                'web_sub_title': self.download.web_sub_title,
                'file_title': self.download.title,
                'volume_id': self.download.volume_id,
                'issue_id': self.download.issue_id,
                'source': self.download.source_name,
                'downloaded_at': round(time()),
                'success': self.download.state != DownloadState.FAILED_STATE
            }
        )
        return

    def add_file_to_database(self) -> None:
        "Register files in database and match to a volume/issue"
        scan_files(
            self.download.volume_id,
            filepath_filter=self.download.files,
            update_websocket=True
        )
        return

    # region Ctx Blocklist
    def add_dl_to_blocklist(self) -> None:
        "Add the download to the blocklist in the database"
        add_to_blocklist(
            self.download.web_link,
            self.download.web_title,
            self.download.web_sub_title,
            self.download.download_link,
            self.download.download_service,
            self.download.volume_id,
            self.download.issue_id,
            BlocklistReason.LINK_BROKEN
        )
        return

    # region Ctx Moving
    def move_to_dest(self) -> None:
        "Move file/fold from download folder to final destination"
        if not exists(self.download.files[0]):
            return

        folder = Volume(self.download.volume_id).vd.folder
        extension = splitext(self.download.files[0])[1].lower()
        if extension not in FileConstants.SCANNABLE_EXTENSIONS:
            extension = ''

        file_dest = join(
            folder,
            self.download.filename_body + extension
        )
        LOGGER.debug(
            f'Moving download to final destination: {self.download}, Dest: {file_dest}'
        )

        # If it takes very long to delete/move the file/folder (because of it's size),
        # the DB is left locked for a long period leading to timeouts.
        commit()

        if exists(file_dest):
            LOGGER.warning(
                f'The file/folder {file_dest} already exists; replacing with downloaded file'
            )
            delete_file_folder(file_dest)

        rename_file(self.download.files[0], file_dest)
        self.download.files = [file_dest]
        return

    def move_torrent_to_dest(self) -> None:
        """
        Move folder downloaded using torrent from download folder to
        final destination, extract files, scan them, rename them.
        """
        if not exists(self.download.files[0]):
            return

        self.move_to_dest()

        self.download.files = extract_files_from_folder(
            self.download.files[0],
            self.download.volume_id
        )

        if not self.download.files:
            return

        scan_files(
            self.download.volume_id,
            filepath_filter=self.download.files,
            update_websocket=True
        )

        rename_files = Settings().sv.rename_downloaded_files
        if rename_files:
            self.download.files = mass_rename(
                self.download.volume_id,
                filepath_filter=self.download.files,
                process_individual_files=False
            )

        return

    def copy_file_torrent(self) -> None:
        "Copy downloaded files to dest. Change download.file to copy."
        if not exists(self.download.files[0]):
            return

        folder = Volume(self.download.volume_id).vd.folder
        file_dest = join(folder, basename(self.download.files[0]))
        LOGGER.debug(
            f'Copying download to final destination: {self.download}, Dest: {file_dest}'
        )

        # If it takes very long to delete/copy the folder (because of it's size),
        # the DB is left locked for a long period leading to timeouts.
        commit()

        if exists(file_dest):
            LOGGER.warning(
                f'The file/folder {file_dest} already exists; replacing with downloaded file'
            )
            delete_file_folder(file_dest)

        copy_directory(self.download.files[0], file_dest)

        self.download.files = extract_files_from_folder(
            file_dest,
            self.download.volume_id
        )

        if not self.download.files:
            return

        scan_files(
            self.download.volume_id,
            filepath_filter=self.download.files,
            update_websocket=True
        )

        rename_files = Settings().sv.rename_downloaded_files
        if rename_files:
            self.download.files = mass_rename(
                self.download.volume_id,
                filepath_filter=self.download.files,
                process_individual_files=False
            )

        return

    # region Ctx Extras
    def delete_file(self) -> None:
        "Delete file from download folder"
        for f in self.download.files:
            delete_file_folder(f)
        return

    def rename_with_proper_extension(self) -> None:
        """
        Rename a file with the proper extension based on mimetype. Rescan files
        in case a rename is done.
        """
        renamed_files: Dict[str, str] = {}
        for idx, file in enumerate(self.download.files):
            if not isfile(file):
                continue

            new_file = set_detected_extension(file)
            if new_file != file:
                rename_file(file, new_file)
                self.download.files[idx] = new_file
                renamed_files[file] = new_file

        if renamed_files:
            FilesDB.update_filepaths(renamed_files)
            commit()

        return

    def convert_file(self) -> None:
        "Convert a file into a different format based on settings"
        if not Settings().sv.convert:
            return

        self.download.files += mass_convert(
            self.download.volume_id,
            self.download.issue_id,
            filepath_filter=self.download.files,
            update_websocket_files=True,
            process_individual_files=False
        )
        return

    def set_file_properties(self) -> None:
        "Process the file to set ownership, permissions and file date"
        mass_process_files(
            self.download.volume_id,
            self.download.issue_id
        )
        return


# region Post-Processors
class PostProcessor:
    def __init__(self, download: Download) -> None:
        self.download = download
        self.ctx = PostProcessingContext(download)
        return

    def success(self) -> None:
        LOGGER.info(
            f'Postprocessing of successful download: {self.download.id}'
        )
        self.ctx.remove_from_queue()
        self.ctx.add_to_history()
        self.ctx.move_to_dest()
        self.ctx.rename_with_proper_extension()
        self.ctx.add_file_to_database()
        self.ctx.convert_file()
        self.ctx.set_file_properties()
        return

    def seeding(self) -> None:
        return

    def canceled(self) -> None:
        LOGGER.info(f'Postprocessing of canceled download: {self.download.id}')
        self.ctx.delete_file()
        self.ctx.remove_from_queue()
        return

    def shutdown(self) -> None:
        LOGGER.info(f'Postprocessing of shut down download: {self.download.id}')
        self.ctx.delete_file()
        return

    def failed(self) -> None:
        LOGGER.info(f'Postprocessing of failed download: {self.download.id}')
        self.ctx.remove_from_queue()
        self.ctx.add_to_history()
        self.ctx.delete_file()
        return

    def perm_failed(self) -> None:
        LOGGER.info(
            f'Postprocessing of permanently failed download: {self.download.id}'
        )
        self.ctx.remove_from_queue()
        self.ctx.add_to_history()
        self.ctx.add_dl_to_blocklist()
        self.ctx.delete_file()
        return


class PostProcessorTorrentsComplete(PostProcessor):
    def success(self) -> None:
        LOGGER.info(
            f'Postprocessing of successful download: {self.download.id}'
        )
        self.ctx.remove_from_queue()
        self.ctx.add_to_history()
        self.ctx.move_torrent_to_dest()
        self.ctx.convert_file()
        self.ctx.set_file_properties()
        return


class PostProcessorTorrentsCopy(PostProcessor):
    def success(self) -> None:
        LOGGER.info(
            f'Postprocessing of successful download: {self.download.id}'
        )
        self.ctx.remove_from_queue()
        self.ctx.delete_file()
        return

    def seeding(self) -> None:
        LOGGER.info(f'Postprocessing of seeding download: {self.download.id}')
        self.ctx.add_to_history()
        self.ctx.copy_file_torrent()
        self.ctx.convert_file()
        self.ctx.set_file_properties()
        self.download.files = self.ctx.original_files
        return
