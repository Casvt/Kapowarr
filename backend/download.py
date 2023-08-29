#-*- coding: utf-8 -*-

"""Handling the download queue and history
"""

import logging
from os import listdir, makedirs, remove
from os.path import basename, join
from threading import Thread
from typing import List, Union

from backend.blocklist import add_to_blocklist
from backend.custom_exceptions import DownloadLimitReached, DownloadNotFound
from backend.db import get_db
from backend.download_clients import Download, DownloadStates, MegaDownload
from backend.getcomics import _extract_download_links, credentials
from backend.post_processing import PostProcessing
from backend.settings import Settings, private_settings


#=====================
# Download handling
#=====================
class DownloadHandler:
	"""Handles downloads
	"""	
	queue: List[Download] = []
	downloading_item: Union[Thread, None] = None
	
	def __init__(self, context) -> None:
		"""Setup the download handler

		Args:
			context (Flask): A flask app instance
		"""		
		self.context = context.app_context
		self.load_download_thread = Thread(target=self.__load_downloads, name="Download Importer")
		return

	def __run_download(self, download: Download) -> None:
		"""Start a download. Intended to be run in a thread.

		Args:
			download (Download): The download to run. One of the entries in self.queue.
		"""	
		logging.info(f'Starting download: {download.id}')

		with self.context():
			try:
				download.run()
			except DownloadLimitReached:
				# Mega download limit reached mid-download
				download.state == DownloadStates.CANCELED_STATE
				self.queue = [e for e in self.queue if not isinstance(e['instance'], MegaDownload)]
			else:
				if download.state == DownloadStates.CANCELED_STATE:
					PostProcessing(download, self.queue).short()
					return

				if download.state == DownloadStates.FAILED_STATE:
					PostProcessing(download, self.queue).error()

				if download.state == DownloadStates.DOWNLOADING_STATE:
					download.state = DownloadStates.IMPORTING_STATE
					PostProcessing(download, self.queue).full()

				self.queue.pop(0)
				self.downloading_item = None

		self._process_queue()
		return

	def _process_queue(self) -> None:
		"""Handle the queue. In the case that there is something in the queue and it isn't already downloading,
		start the download. This can safely be called multiple times while a download is going or while there is
		nothing in the queue.
		"""
		if not self.queue or self.downloading_item:
			return

		# First entry in queue is not downloading at this point
		self.downloading_item = Thread(target=self.__run_download, args=(self.queue[0],), name="Download Handler")
		self.downloading_item.start()
		
		return

	def __load_downloads(self) -> None:
		"""Load downloads from the database and add them to the queue for re-downloading
		"""
		logging.debug('Loading downloads from database')
		with self.context():
			cursor = get_db('dict', temp=True)
			cursor.execute("""
				SELECT
					id,
					link,
					volume_id, issue_id
				FROM download_queue;
			""")
			for download in cursor:
				logging.debug(f'Download from database: {dict(download)}')
				self.add(download['link'], download['volume_id'], download['issue_id'], download['id'])
			cursor.connection.close()
		return

	def add(self,
		link: str,
		volume_id: int, issue_id: int=None,
		_download_db_id_override: int=None
	) -> List[dict]:
		"""Add a download to the queue

		Args:
			link (str): A getcomics link to download from
			volume_id (int): The id of the volume for which the download is intended
			issue_id (int, optional): The id of the issue for which the download is intended. Defaults to None.
			_download_db_id_override (int, optional): Internal use only. Map download to an already existing entry in the database. Defaults to None.

		Returns:
			List[dict]: Queue entries that were added from the link.
		"""		
		logging.info(
			f'Adding download for volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: {link}'
		)

		is_gc_link = link.startswith(private_settings['getcomics_url'])

		downloads: List[Download] = []
		if is_gc_link:
			# Extract download links and convert into Download instances
			GC_downloads, limit_reached = _extract_download_links(link, volume_id, issue_id)
			if not GC_downloads:
				if not limit_reached:
					# No links extracted from page so add it to blocklist
					add_to_blocklist(link, 3)
				logging.warning('Unable to extract download links from source')
				if _download_db_id_override:
					get_db().execute(
						"DELETE FROM download_queue WHERE id = ?",
						(_download_db_id_override,)
					)
				return []
			downloads = GC_downloads

		result = []
		# Register download in database
		db_id = _download_db_id_override or get_db().execute("""
			INSERT INTO download_queue(link, volume_id, issue_id)
			VALUES (?,?,?);
			""",
			(link, volume_id, issue_id)
		).lastrowid

		for download in downloads:
			download.id = self.queue[-1].id + 1 if self.queue else 1
			download.db_id = db_id
			download.volume_id = volume_id
			download.issue_id = issue_id
			download.page_link = link if is_gc_link else None

			# Add to queue
			result.append(download.todict())
			self.queue.append(download)

		self._process_queue()
		return result

	def stop_handle(self) -> None:
		"""Cancel any running download and stop the handler
		"""		
		logging.debug('Stopping download thread')
		if self.downloading_item:
			self.queue[0].stop()
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

		# Delete download from queue
		for download in self.queue:
			if download.id == download_id:
				if download.state == DownloadStates.DOWNLOADING_STATE:
					download.stop()
					self.downloading_item.join()
					self.downloading_item = None
				self.queue.remove(download)
				PostProcessing(download, self.queue)._remove_from_queue()
				break
		else:
			raise DownloadNotFound

		self._process_queue()
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
		ghost_files = [join(folder, f) for f in files_in_folder if not f in files_in_queue]
		for f in ghost_files:
			remove(f)
		return

#=====================
# Download History Managing
#=====================
def get_download_history(offset: int=0) -> List[dict]:
	"""Get the download history in blocks of 50.

	Args:
		offset (int, optional): The offset of the list. The higher the number, the deeper into history you go. Defaults to 0.

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
