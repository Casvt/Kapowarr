#-*- coding: utf-8 -*-

"""
Handling the download queue and history
"""

from __future__ import annotations

from os import listdir
from os.path import basename, join
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Dict, List, Tuple, Type, Union

from backend.blocklist import add_to_blocklist
from backend.custom_exceptions import (DownloadLimitReached, DownloadNotFound,
                                       LinkBroken)
from backend.db import get_db
from backend.download_direct_clients import (DirectDownload, Download,
                                             MegaDownload)
from backend.download_torrent_clients import TorrentClients, TorrentDownload
from backend.enums import (BlocklistReason, DownloadState, FailReason,
                           SeedingHandling)
from backend.files import create_folder, delete_file_folder
from backend.getcomics import extract_GC_download_links
from backend.helpers import first_of_column
from backend.logging import LOGGER
from backend.post_processing import (PostProcesser,
                                     PostProcesserTorrentsComplete,
                                     PostProcesserTorrentsCopy)
from backend.server import WebSocket
from backend.settings import Settings, private_settings

if TYPE_CHECKING:
	from flask import Flask

#=====================
# Download handling
#=====================
download_type_to_class: Dict[str, Type[Download]] = {
	c.type: c
	for c in Download.__subclasses__()[0].__subclasses__()
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
		torrent_clients = first_of_column(
			get_db().execute(
				"SELECT id FROM torrent_clients;"
			)
		)
		queue_ids = [
			d.client.id
			for d in self.queue
			if isinstance(d, TorrentDownload)
		]
		sorted_list = sorted(torrent_clients, key=lambda c: queue_ids.count(c))
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
			seeding_handling = settings['seeding_handling']

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
					download.remove_from_client(delete_files=True)
					post_processer.shutdown(download)
					break

				elif (
					seeding_handling == SeedingHandling.COPY
					and download.state == DownloadState.SEEDING_STATE
					and not files_copied
				):
					files_copied = True
					post_processer.seeding(download)

				elif download.state == DownloadState.IMPORTING_STATE:
					if settings['delete_completed_torrents']:
						download.remove_from_client(delete_files=False)
					post_processer.success(download)
					self.queue.remove(download)
					break

				else:
					# Queued, downloading or
					# seeding with files copied or seeding_handling = 'complete'
					sleep(private_settings['torrent_update_interval'])

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
				if isinstance(e, (DirectDownload, MegaDownload))
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
			download.page_link = page_link

			if download.id is None:
				download.id = cursor.execute("""
					INSERT INTO download_queue(
						client_type, torrent_client_id,
						link, filename_body, source,
						volume_id, issue_id, page_link
					)
					VALUES (?, ?, ?, ?, ?, ?, ?, ?);
					""",
					(
						download.type,
						None,
						download.download_link,
						download._filename_body,
						download.source,
						download.volume_id,
						download.issue_id,
						download.page_link
					)
				).lastrowid

			if isinstance(download, TorrentDownload):
				if download.client is None:
					download.client = TorrentClients.get_client(
						self.__choose_torrent_client()
					)
					cursor.execute("""
						UPDATE download_queue
						SET torrent_client_id = ?
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
			cursor = get_db(dict)
			downloads = cursor.execute("""
				SELECT
					id, client_type, torrent_client_id,
					link, filename_body, source,
					volume_id, issue_id, page_link
				FROM download_queue;
			""").fetchall()

			if downloads:
				LOGGER.info('Loading downloads')

			for download in downloads:
				LOGGER.debug(f'Download from database: {dict(download)}')
				try:
					dl_instance = download_type_to_class[download['client_type']](
						link=download['link'],
						filename_body=download['filename_body'],
						source=download['source'],
						custom_name=True
					)
					dl_instance.id = download['id']
					if isinstance(dl_instance, TorrentDownload):
						dl_instance.client = TorrentClients.get_client(
							download['torrent_client_id']
						)

				except LinkBroken as lb:
					# Link is broken
					add_to_blocklist(download['link'], lb.reason)
					cursor.execute(
						"DELETE FROM download_queue WHERE id = ?;",
						(download['id'],)
					)
					# Link is broken, which triggers a write to the database
					# To avoid the database being locked for a long time while
					# importing, we commit in-between.
					cursor.connection.commit()
					continue

				except DownloadLimitReached:
					continue

				self.queue += self.__prepare_downloads_for_queue(
					[dl_instance],
					download['volume_id'],
					download['issue_id'],
					download['page_link']
				)
				# self.__prepare_downloads_for_queue() has a write to the db
				# To avoid locking the db, commit in-between.
				cursor.connection.commit()

			self._process_queue()
		return

	def add(self,
		link: str,
		volume_id: int,
		issue_id: Union[int, None] = None
	) -> Tuple[List[dict], Union[FailReason, None]]:
		"""Add a download to the queue

		Args:
			link (str): A getcomics link to download from
			volume_id (int): The id of the volume for which the download is intended
			issue_id (Union[int, None], optional): The id of the issue for which
			the download is intended.
				Defaults to None.

		Returns:
			Tuple[List[dict], Union[FailReason, None]]:
			Queue entries that were added from the link and reason for failing
			if no entries were added.
		"""
		LOGGER.info(
			'Adding download for '
			+ f'volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: {link}'
		)

		# Check if link isn't already in queue
		if any(d for d in self.queue if link in (d.page_link, d.download_link)):
			LOGGER.info('Download already in queue')
			return [], None

		is_gc_link = link.startswith(private_settings['getcomics_url'])

		downloads: List[Download] = []
		if is_gc_link:
			# Extract download links and convert into Download instances
			GC_downloads, fail_reason = extract_GC_download_links(
				link,
				volume_id,
				issue_id
			)

			if fail_reason:
				if fail_reason == FailReason.BROKEN:
					# Can't even fetch the GC page
					add_to_blocklist(link, BlocklistReason.LINK_BROKEN)

				elif fail_reason == FailReason.NO_WORKING_LINKS:
					# Page has links that matched but all are broken
					add_to_blocklist(link, BlocklistReason.NO_WORKING_LINKS)

				LOGGER.warning(
					f'Unable to extract download links from source; fail_reason="{fail_reason.value}"'
				)
				return [], fail_reason

			downloads = GC_downloads

		result = self.__prepare_downloads_for_queue(
			downloads,
			volume_id,
			issue_id,
			link if is_gc_link else None
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

	def remove(self, download_id: int) -> None:
		"""Remove a download entry from the queue

		Args:
			download_id (int): The id of the download to remove from the queue

		Raises:
			DownloadNotFound: The id doesn't map to any download in the queue
		"""
		LOGGER.info(f'Removing download with id {download_id}')

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

				break
		else:
			raise DownloadNotFound

		return

	def create_download_folder(self) -> None:
		"""
		Create the download folder if it doesn't already.
		"""
		create_folder(Settings()['download_folder'])
		return

	def empty_download_folder(self) -> None:
		"""
		Empty the temporary download folder of files that aren't being downloaded.
		Handy in the case that a crash left half-downloaded files behind in the folder.
		"""
		LOGGER.info(f'Emptying the temporary download folder')
		folder = Settings()['download_folder']
		files_in_queue = [basename(download.file) for download in self.queue]
		files_in_folder = listdir(folder)
		ghost_files = [
			join(folder, f)
			for f in files_in_folder
			if not f in files_in_queue
		]
		for f in ghost_files:
			delete_file_folder(f)
		return

#=====================
# Download History Managing
#=====================
def get_download_history(offset: int=0) -> List[dict]:
	"""Get the download history in blocks of 50.

	Args:
		offset (int, optional): The offset of the list.
		The higher the number, the deeper into history you go.
			Defaults to 0.

	Returns:
		List[dict]: The history entries.
	"""
	result = list(map(
		dict,
		get_db(dict).execute(
			"""
			SELECT
				original_link, title, downloaded_at
			FROM download_history
			ORDER BY downloaded_at DESC
			LIMIT 50
			OFFSET ?;
			""",
			(offset * 50,)
		)
	))
	return result

def delete_download_history() -> None:
	"""
	Delete complete download history
	"""
	LOGGER.info('Deleting download history')
	get_db().execute("DELETE FROM download_history;")
	return
