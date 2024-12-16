# -*- coding: utf-8 -*-

"""
Handling the download queue and history
"""

from __future__ import annotations

from asyncio import run
from os import listdir
from os.path import basename, join
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Type, Union

from backend.base.custom_exceptions import (DownloadLimitReached,
                                            DownloadNotFound, FailedGCPage,
                                            LinkBroken)
from backend.base.definitions import (BlocklistReason, Constants,
                                      Download, DownloadSource,
                                      DownloadState, ExternalDownload,
                                      FailReason, SeedingHandling)
from backend.base.files import create_folder, delete_file_folder
from backend.base.helpers import first_of_column
from backend.base.logging import LOGGER
from backend.features.post_processing import (PostProcesser,
                                              PostProcesserTorrentsComplete,
                                              PostProcesserTorrentsCopy)
from backend.implementations.blocklist import add_to_blocklist
from backend.implementations.download_clients import (BaseDirectDownload,
                                                      MegaDownload,
                                                      TorrentDownload)
from backend.implementations.external_clients import ExternalClients
from backend.implementations.getcomics import GetComicsPage
from backend.internals.db import get_db, iter_commit
from backend.internals.server import WebSocket
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from flask import Flask

# =====================
# Download handling
# =====================
download_type_to_class: Dict[str, Type[Download]] = {
    c.type: c
    for c in (
        *BaseDirectDownload.__subclasses__(),
        *ExternalDownload.__subclasses__()
    )
}


class DownloadHandler:
    queue: List[Download] = []
    downloading_item: Union[Thread, None] = None

    def __init__(self, context: Flask) -> None:
        """Setup the download handler

        Args:
            context (Flask): A flask app instance
        """
        self.context = context.app_context
        self.load_download_thread = Thread(
            target=self.__load_downloads,
            name="Download Importer"
        )
        return

    def __choose_torrent_client(self) -> int:
        """Get the ID of the torrent client with the least downloads

        Returns:
            int: The ID of the client
        """
        external_clients = (
            client["id"]
            for client in ExternalClients.get_clients()
        )
        queue_ids = [
            d.client.id
            for d in self.queue
            if isinstance(d, TorrentDownload)
        ]
        sorted_list = sorted(
            external_clients,
            key=lambda c: queue_ids.count(c)
        )
        return sorted_list[0]

    def __run_download(self, download: Download) -> None:
        """Start a download. Intended to be run in a thread.

        Args:
            download (Download): The download to run.
                One of the entries in self.queue.
        """
        LOGGER.info(f'Starting download: {download.id}')

        with self.context():
            ws = WebSocket()
            try:
                download.run()

            except DownloadLimitReached:
                # Mega download limit reached mid-download
                download.state = DownloadState.FAILED_STATE
                ws.update_queue_status(download)
                for d in self.queue:
                    if (isinstance(d, MegaDownload)
                    and d != download):
                        self.queue.remove(d)
                        ws.send_queue_ended(d)

            ws.update_queue_status(download)
            if download.state == DownloadState.CANCELED_STATE:
                PostProcesser.canceled(download)

            elif download.state == DownloadState.FAILED_STATE:
                PostProcesser.failed(download)

            elif download.state == DownloadState.SHUTDOWN_STATE:
                PostProcesser.shutdown(download)
                return

            elif download.state == DownloadState.DOWNLOADING_STATE:
                download.state = DownloadState.IMPORTING_STATE
                ws.update_queue_status(download)
                PostProcesser.success(download)

            self.queue.remove(download)
            self.downloading_item = None
            ws.send_queue_ended(download)

        self._process_queue()
        return

    def __run_torrent_download(self, download: TorrentDownload) -> None:
        """Start a torrent download. Intended to be run in a thread.

        Args:
            download (TorrentDownload): The torrent download to run.
                One of the entries in self.queue.
        """
        download.run()

        with self.context():
            ws = WebSocket()
            settings = Settings()
            seeding_handling = settings.sv.seeding_handling

            if seeding_handling == SeedingHandling.COMPLETE:
                post_processer = PostProcesserTorrentsComplete
            elif seeding_handling == SeedingHandling.COPY:
                post_processer = PostProcesserTorrentsCopy
            else:
                raise NotImplementedError

            # When seeding_handling is 'copy', keep track if we already copied
            # the files
            files_copied = False

            while True:
                download.update_status()
                ws.update_queue_status(download)

                if download.state == DownloadState.CANCELED_STATE:
                    download.remove_from_client(delete_files=True)
                    post_processer.canceled(download)
                    self.queue.remove(download)
                    break

                elif download.state == DownloadState.FAILED_STATE:
                    download.remove_from_client(delete_files=True)
                    post_processer.failed(download)
                    self.queue.remove(download)
                    break

                elif download.state == DownloadState.SHUTDOWN_STATE:
                    break

                elif (
                    seeding_handling == SeedingHandling.COPY
                    and download.state == DownloadState.SEEDING_STATE
                    and not files_copied
                ):
                    files_copied = True
                    post_processer.seeding(download)

                elif download.state == DownloadState.IMPORTING_STATE:
                    if settings.sv.delete_completed_torrents:
                        download.remove_from_client(delete_files=False)
                    post_processer.success(download)
                    self.queue.remove(download)
                    break

                else:
                    # Queued, downloading or
                    # seeding with files copied or seeding_handling = 'complete'
                    sleep(Constants.TORRENT_UPDATE_INTERVAL)

            ws.send_queue_ended(download)
        return

    def _process_queue(self) -> None:
        """
        Handle the queue. In the case that there is something in the queue
        and it isn't already downloading, start the download. This can safely be
        called multiple times while a download is going or while there is nothing
        in the queue.
        """
        if not self.queue or self.downloading_item:
            return

        first_direct_download = next(
            (
                e
                for e in self.queue
                if isinstance(e, BaseDirectDownload)
            ),
            None
        )
        if not first_direct_download:
            return

        # First entry in queue is not downloading at this point
        self.downloading_item = Thread(
            target=self.__run_download,
            args=(first_direct_download,),
            name="Download Handler"
        )
        self.downloading_item.start()

        return

    def __prepare_downloads_for_queue(
        self,
        downloads: List[Download],
        volume_id: int,
        issue_id: Union[int, None],
        page_link: Union[str, None]
    ) -> List[Download]:
        """Get download instances ready to be put in the queue.
        Registers them in the db if not already. For torrents,
        it chooses the client, creates the thread and runs it.

        Args:
            downloads (List[Download]): The downloads to get ready.

            volume_id (int): The ID of the volume that the downloads are for.

            issue_id (int): The ID of the issue that the downloads are for.
                Default is None.

            page_link (Union[str, None]): The link to the page where the
            download was grabbed from.

        Returns:
            List[Download]: The downloads, now prepared.
        """
        cursor = get_db()
        for download in downloads:
            download.volume_id = volume_id
            download.issue_id = issue_id
            download.web_link = page_link

            if download.id is None:
                download.id = cursor.execute(
                    """
                    INSERT INTO download_queue(
                        client_type, external_client_id,
                        download_link, filename_body, source,
                        volume_id, issue_id,
                        web_link, web_title, web_sub_title
                    )
                    VALUES (
                        ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?
                    );
                    """,
                    (
                        download.type,
                        None,
                        download.download_link,
                        download._filename_body,
                        download.source.value,
                        download.volume_id,
                        download.issue_id,
                        download.web_link,
                        download.web_title,
                        download.web_sub_title
                    )
                ).lastrowid

            if isinstance(download, TorrentDownload):
                if download.client is None:
                    download.client = ExternalClients.get_client(
                        self.__choose_torrent_client()
                    )
                    cursor.execute("""
                        UPDATE download_queue
                        SET external_client_id = ?
                        WHERE id = ?;
                        """,
                        (download.client.id, download.id)
                    )

                download._download_thread = Thread(
                    target=self.__run_torrent_download,
                    args=(download,),
                    name='Torrent Download Handler'
                )
                download._download_thread.start()
            WebSocket().send_queue_added(download)
        return downloads

    def __load_downloads(self) -> None:
        """
        Load downloads from the database and add them to the queue
        for re-downloading
        """
        with self.context():
            cursor = get_db()
            downloads = cursor.execute("""
                SELECT
                    id, client_type, external_client_id,
                    download_link, filename_body, source,
                    volume_id, issue_id,
                    web_link, web_title, web_sub_title
                FROM download_queue;
            """).fetchall()

            if downloads:
                LOGGER.info('Loading downloads')

            for download in iter_commit(downloads):
                LOGGER.debug(f'Download from database: {dict(download)}')
                try:
                    dl_instance = download_type_to_class[download['client_type']](
                        download_link=download['download_link'],
                        filename_body=download['filename_body'],
                        source=DownloadSource(download['source']),
                        custom_name=True
                    )
                    dl_instance.id = download['id']
                    dl_instance.web_title = download['web_title']
                    dl_instance.web_sub_title = download['web_sub_title']
                    if isinstance(dl_instance, TorrentDownload):
                        dl_instance.client = ExternalClients.get_client(
                            download['external_client_id']
                        )

                except LinkBroken as lb:
                    # Link is broken
                    add_to_blocklist(
                        web_link=download['web_link'],
                        web_title=download['web_title'],
                        web_sub_title=download['web_sub_title'],
                        download_link=download['download_link'],
                        source=DownloadSource(download['source']),
                        volume_id=download['volume_id'],
                        issue_id=download['issue_id'],
                        reason=lb.reason
                    )
                    cursor.execute(
                        "DELETE FROM download_queue WHERE id = ?;",
                        (download['id'],)
                    )
                    continue

                except DownloadLimitReached:
                    continue

                self.queue += self.__prepare_downloads_for_queue(
                    [dl_instance],
                    download['volume_id'],
                    download['issue_id'],
                    download['web_link']
                )

            self._process_queue()
        return

    def __determine_link_type(self, link: str) -> Union[str, None]:
        if link.startswith(Constants.GC_SITE_URL):
            return 'gc'
        return None

    def link_in_queue(self, link: str) -> bool:
        return any(
            d
            for d in self.queue
            if link in (d.web_link, d.download_link)
        )

    def add(self,
        link: str,
        volume_id: int,
        issue_id: Union[int, None] = None,
        force_match: bool = False
    ) -> Tuple[List[dict], Union[FailReason, None]]:
        """Add a download to the queue.

        Args:
            link (str): A getcomics link to download from.

            volume_id (int): The id of the volume for which the download is
            intended.

            issue_id (Union[int, None], optional): The id of the issue for which
            the download is intended.
                Defaults to None.

            force_match (bool, optional): On sources where downloads are
            filtered, skip this and instead download everything.
                Defaults to False.

        Returns:
            Tuple[List[dict], Union[FailReason, None]]:
            Queue entries that were added from the link and reason for failing
            if no entries were added.
        """
        LOGGER.info(
            'Adding download for ' +
            f'volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: ' +
            f'{link}'
        )

        if self.link_in_queue(link):
            LOGGER.info('Download already in queue')
            return [], None

        link_type = self.__determine_link_type(link)
        downloads: List[Download] = []
        if link_type == 'gc':
            try:
                gcp = GetComicsPage(link)
                run(gcp.load_data())
                downloads = run(gcp.create_downloads(
                    volume_id, issue_id, force_match
                ))

            except FailedGCPage as e:
                if e.reason == FailReason.BROKEN:
                    add_to_blocklist(
                        web_link=link,
                        web_title=None,
                        web_sub_title=None,
                        download_link=None,
                        source=None,
                        volume_id=volume_id,
                        issue_id=issue_id,
                        reason=BlocklistReason.LINK_BROKEN
                    )

                elif e.reason == FailReason.NO_WORKING_LINKS:
                    add_to_blocklist(
                        web_link=link,
                        web_title=gcp.web_title, # type: ignore
                        web_sub_title=None,
                        download_link=None,
                        source=None,
                        volume_id=volume_id,
                        issue_id=issue_id,
                        reason=BlocklistReason.NO_WORKING_LINKS
                    )

                LOGGER.warning(
                    f'Unable to extract download links from source; fail_reason="{e.reason.value}"'
                )
                return [], e.reason

        result = self.__prepare_downloads_for_queue(
            downloads,
            volume_id,
            issue_id,
            link if link_type == 'gc' else None
        )
        self.queue += result

        self._process_queue()
        return [r.todict() for r in result], None

    def stop_handle(self) -> None:
        """
        Cancel any running download and stop the handler
        """
        LOGGER.debug('Stopping download thread')

        for e in self.queue:
            e.stop(DownloadState.SHUTDOWN_STATE)

        if self.downloading_item:
            self.downloading_item.join()

        for e in self.queue:
            if not isinstance(e, ExternalDownload) or not e._download_thread:
                continue
            e._download_thread.join()

        return

    def get_all(self) -> List[dict]:
        """Get all queue entries

        Returns:
            List[dict]: All queue entries, formatted using `Download.todict()`.
        """
        return [e.todict() for e in self.queue]

    def get_one(self, download_id: int) -> dict:
        """Get a queue entry based on it's id.

        Args:
            download_id (int): The id of the download to fetch

        Raises:
            DownloadNotFound: The id doesn't map to any download in the queue

        Returns:
            dict: The queue entry, formatted using `Download.todict()`.
        """
        for entry in self.queue:
            if entry.id == download_id:
                return entry.todict()
        raise DownloadNotFound

    def remove(self, download_id: int, blocklist: bool = False) -> None:
        """Remove a download entry from the queue.

        Args:
            download_id (int): The id of the download to remove from the queue.

            blocklist (bool, optional): Add the page link to the blocklist.
                Defaults to False.

        Raises:
            DownloadNotFound: The id doesn't map to any download in the queue.
        """
        LOGGER.info(f'Removing download with id {download_id} and {blocklist=}')

        for download in self.queue:
            if download.id == download_id:
                prev_state = download.state
                download.stop()

                if prev_state == DownloadState.QUEUED_STATE:
                    WebSocket().update_queue_status(download)
                    if isinstance(download, TorrentDownload):
                        download.remove_from_client(delete_files=True)
                        PostProcesserTorrentsComplete.canceled(download)
                    else:
                        self.queue.remove(download)
                        PostProcesser.canceled(download)
                    WebSocket().send_queue_ended(download)

                if blocklist:
                    add_to_blocklist(
                        web_link=download.web_link,
                        web_title=download.web_title,
                        web_sub_title=download.web_sub_title,
                        download_link=download.download_link,
                        source=download.source,
                        volume_id=download.volume_id,
                        issue_id=download.issue_id,
                        reason=BlocklistReason.ADDED_BY_USER
                    )

                break
        else:
            raise DownloadNotFound

        return

    def remove_all(self) -> None:
        """
        Remove all downloads from the queue
        """
        for download in self.queue[::-1]:
            self.remove(download.id)
        return

    def create_download_folder(self) -> None:
        """
        Create the download folder if it doesn't already.
        """
        create_folder(Settings().sv.download_folder)
        return

    def empty_download_folder(self) -> None:
        """
        Empty the temporary download folder of files that aren't being downloaded.
        Handy in the case that a crash left half-downloaded files behind in the folder.
        """
        LOGGER.info(f'Emptying the temporary download folder')
        folder = Settings().sv.download_folder
        files_in_queue = [basename(download.file) for download in self.queue]
        files_in_folder = listdir(folder)
        ghost_files = [
            join(folder, f)
            for f in files_in_folder
            if f not in files_in_queue
        ]
        for f in ghost_files:
            delete_file_folder(f)
        return

# =====================
# Download History Managing
# =====================


def get_download_history(
    volume_id: Union[int, None] = None,
    issue_id: Union[int, None] = None,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get the download history in blocks of 50.

    Args:
        volume_id (Union[int, None], optional): Get the history of a specific
        volume.
            Defaults to None.

        issue_id (Union[int, None], optional): Get the history of a specific
        issue. No need to supply volume_id in order to get issue history.
            Defaults to None.

        offset (int, optional): The offset of the list.
        The higher the number, the deeper into history you go.
            Defaults to 0.

    Returns:
        List[Dict[str, Any]]: The history entries.
    """
    if issue_id is not None:
        comm = ("""
            SELECT
                web_link, web_title, web_sub_title,
                file_title,
                volume_id, issue_id,
                source, downloaded_at
            FROM download_history
            WHERE issue_id = ?
            ORDER BY downloaded_at DESC
            LIMIT 50
            OFFSET ?;
            """,
            (issue_id, offset * 50)
        )

    elif volume_id is not None:
        comm = ("""
            SELECT
                web_link, web_title, web_sub_title,
                file_title,
                volume_id, issue_id,
                source, downloaded_at
            FROM download_history
            WHERE volume_id = ?
            ORDER BY downloaded_at DESC
            LIMIT 50
            OFFSET ?;
            """,
            (volume_id, offset * 50)
        )

    else:
        comm = ("""
            SELECT
                web_link, web_title, web_sub_title,
                file_title,
                volume_id, issue_id,
                source, downloaded_at
            FROM download_history
            ORDER BY downloaded_at DESC
            LIMIT 50
            OFFSET ?;
            """,
            (offset * 50,)
        )

    return get_db().execute(*comm).fetchalldict()


def delete_download_history() -> None:
    """
    Delete complete download history
    """
    LOGGER.info("Deleting download history")
    get_db().execute("DELETE FROM download_history;")
    return
