#-*- coding: utf-8 -*-

"""Handling the download queue and history
"""

import logging
from os import listdir, makedirs, remove
from os.path import basename, join
from threading import Thread
from time import sleep
from typing import Dict, List, Union

from backend.blocklist import add_to_blocklist
from backend.custom_exceptions import (DownloadLimitReached, DownloadNotFound,
                                       LinkBroken)
from backend.db import get_db
from backend.download_direct_clients import (DirectDownload, Download,
                                             MegaDownload)
from backend.download_general import DownloadStates
from backend.download_torrent_clients import TorrentClients, TorrentDownload
from backend.getcomics import _extract_download_links
from backend.post_processing import PostProcesser, PostProcesserTorrents
from backend.settings import Settings, private_settings

#=====================
# Download handling
#=====================
download_type_to_class: Dict[str, Download] = {
	c.type: c
	for c in Download.__subclasses__()[0].__subclasses__()
}

class DownloadHandler:
	queue: List[Download] = []
	downloading_item: Union[Thread, None] = None
	
	def __init__(self, context) -> None:
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
		torrent_clients = [
			tc[0]
			for tc in get_db().execute(
				"SELECT id FROM torrent_clients;"
			)
		]
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
		logging.info(f'Starting download: {download.id}')

		with self.context():
			try:
				download.run()

			except DownloadLimitReached:
				# Mega download limit reached mid-download
				download.state = DownloadStates.FAILED_STATE
				self.queue = [
					e
					for e in self.queue
					if (
						not isinstance(e['instance'], MegaDownload)
						or e == download
					)
				]

			if download.state == DownloadStates.CANCELED_STATE:
				PostProcesser.canceled(download)

			elif download.state == DownloadStates.FAILED_STATE:
				PostProcesser.failed(download)
			
			elif download.state == DownloadStates.SHUTDOWN_STATE:
				PostProcesser.shutdown(download)
				return

			elif download.state == DownloadStates.DOWNLOADING_STATE:
				download.state = DownloadStates.IMPORTING_STATE
				PostProcesser.success(download)

			self.queue.remove(download)
			self.downloading_item = None

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
			while True:
				download.update_status()

				if download.state in (
					DownloadStates.QUEUED_STATE,
					DownloadStates.DOWNLOADING_STATE,
					DownloadStates.SEEDING_STATE
				):
					sleep(private_settings['torrent_update_interval'])
					continue

				if download.state == DownloadStates.CANCELED_STATE:
					download.remove_from_client(delete_files=True)
					PostProcesserTorrents.canceled(download)

				elif download.state == DownloadStates.FAILED_STATE:
					download.remove_from_client(delete_files=True)
					PostProcesserTorrents.failed(download)
				
				elif download.state == DownloadStates.SHUTDOWN_STATE:
					download.remove_from_client(delete_files=True)
					PostProcesserTorrents.shutdown(download)
					return

				elif download.state == DownloadStates.IMPORTING_STATE:
					download.remove_from_client(delete_files=False)
					PostProcesserTorrents.success(download)

				self.queue.remove(download)
				return

	def _process_queue(self) -> None:
		"""Handle the queue. In the case that there is something in the queue
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
		issue_id: int,
		page_link: Union[str, None]
	) -> List[Download]:
		
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
		return downloads

	def __load_downloads(self) -> None:
		"""Load downloads from the database and add them to the queue
		for re-downloading
		"""
		with self.context():
			cursor = get_db('dict')
			downloads = cursor.execute("""
				SELECT
					id, client_type, torrent_client_id,
					link, filename_body, source,
					volume_id, issue_id, page_link
				FROM download_queue;
			""").fetchall()

			if downloads:
				logging.info('Loading downloads')

			for download in downloads:
				logging.debug(f'Download from database: {dict(download)}')
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
					add_to_blocklist(download['link'], lb.reason_id)
					# Link is broken, which triggers a write to the database
					# To avoid the database being locked for a long time while 
					# importing, we commit in-between.
					cursor.connection.commit()

				except DownloadLimitReached:
					continue

				self.queue += self.__prepare_downloads_for_queue(
					[dl_instance],
					download['volume_id'],
					download['issue_id'],
					download['page_link']
				)

			self._process_queue()
		return

	def add(self,
		link: str,
		volume_id: int,
		issue_id: int=None
	) -> List[dict]:
		"""Add a download to the queue

		Args:
			link (str): A getcomics link to download from
			volume_id (int): The id of the volume for which the download is intended
			issue_id (int, optional): The id of the issue for which the download
			is intended.
				Defaults to None.

		Returns:
			List[dict]: Queue entries that were added from the link.
		"""		
		logging.info(
			'Adding download for '
			+ f'volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: {link}'
		)

		# Check if link isn't already in queue
		if any(d for d in self.queue if link in (d.page_link, d.download_link)):
			logging.info('Download already in queue')
			return []

		is_gc_link = link.startswith(private_settings['getcomics_url'])

		downloads: List[Download] = []
		if is_gc_link:
			# Extract download links and convert into Download instances
			GC_downloads, limit_reached = _extract_download_links(
				link,
				volume_id,
				issue_id
			)

			if not GC_downloads:
				if not limit_reached:
					# No links extracted from page so add it to blocklist
					add_to_blocklist(link, 3)
				logging.warning(
					f'Unable to extract download links from source; {limit_reached=}'
				)
				return []

			downloads = GC_downloads

		result = self.__prepare_downloads_for_queue(
			downloads,
			volume_id,
			issue_id,
			link if is_gc_link else None
		)
		self.queue += result

		self._process_queue()
		return [r.todict() for r in result]

	def stop_handle(self) -> None:
		"""Cancel any running download and stop the handler
		"""		
		logging.debug('Stopping download thread')

		for e in self.queue:
			e.stop(DownloadStates.SHUTDOWN_STATE)

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
			if entry['id'] == download_id:
				return entry.todict()
		raise DownloadNotFound

	def remove(self, download_id: int) -> None:
		"""Remove a download entry from the queue

		Args:
			download_id (int): The id of the download to remove from the queue

		Raises:
			DownloadNotFound: The id doesn't map to any download in the queue
		"""	
		logging.info(f'Removing download with id {download_id}')

		for download in self.queue:
			if download.id == download_id:
				download.stop()
				break
		else:
			raise DownloadNotFound

		return

	def create_download_folder(self) -> None:
		"""Create the download folder if it doesn't already.
		"""
		makedirs(Settings().get_settings()['download_folder'], exist_ok=True)
		return

	def empty_download_folder(self) -> None:
		"""Empty the temporary download folder of files that aren't being downloaded.
		Handy in the case that a crash left half-downloaded files behind in the folder.
		"""
		logging.info(f'Emptying the temporary download folder')
		folder = Settings().get_settings()['download_folder']
		files_in_queue = [basename(download.file) for download in self.queue]
		files_in_folder = listdir(folder)
		ghost_files = [
			join(folder, f)
			for f in files_in_folder
			if not f in files_in_queue
		]
		for f in ghost_files:
			remove(f)
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
		get_db('dict').execute(
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
	"""Delete complete download history
	"""
	logging.info('Deleting download history')
	get_db().execute("DELETE FROM download_history;")
	return
