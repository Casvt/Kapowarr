#-*- coding: utf-8 -*-

"""
Clients for downloading from a direct URL and Mega.
Used when downloading from GC.
"""

from os.path import basename, join, sep, splitext
from re import IGNORECASE, compile
from time import perf_counter
from urllib.parse import unquote_plus

from requests import RequestException, get, post
from requests.exceptions import ChunkedEncodingError

from backend.credentials import Credentials
from backend.custom_exceptions import LinkBroken
from backend.download_general import Download
from backend.enums import BlocklistReason, DownloadState
from backend.helpers import WebSocket
from backend.logging import LOGGER
from backend.settings import Settings

from .lib.mega import Mega, RequestError, sids

file_extension_regex = compile(r'(?<=\.|\/)[\w\d]{2,4}(?=$|;|\s|\")', IGNORECASE)
credentials = Credentials(sids)
download_chunk_size = 4194304 # 4MB Chunks
MEDIAFIRE_FOLDER_LINK = "https://www.mediafire.com/api/1.5/file/zip.php"

class BaseDownload(Download):
	def __init__(self):
		self.id = None # type: ignore
		self.state: DownloadState = DownloadState.QUEUED_STATE

	def todict(self) -> dict:
		"""Represent the download in the form of a dict

		Returns:
			dict: The dict with all relevant info about the download
		"""
		return {
			'id': self.id,
			'volume_id': self.volume_id,
			'issue_id': self.issue_id,

			'page_link': self.page_link,
			'source': self.source,
			'download_link': self.download_link,
			'type': self.type,

			'file': self.file,
			'title': self.title,
			'size': self.size,

			'status': self.state.value,
			'progress': self.progress,
			'speed': self.speed,
		}

	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}, {self.download_link}, {self.file}>'

class DirectDownload(BaseDownload):
	"For downloading a file directly from a link"

	type = 'direct'

	def __init__(self,
		link: str,
		filename_body: str,
		source: str,
		custom_name: bool=True
	):
		"""Setup the direct download

		Args:
			link (str): The link (that leads to a file) that should be used
			filename_body (str): The body of the filename to write to
			source (str): The name of the source of the link
			custom_name (bool, optional): If the name supplied should be used
			or the default filename.
				Defaults to True.

		Raises:
			LinkBroken: The link doesn't work
		"""
		LOGGER.debug(f'Creating download: {link}, {filename_body}')
		super().__init__()
		self.progress: float = 0.0
		self.speed: float = 0.0
		self.size: int = 0
		self.download_link = link
		self.source = source

		try:
			r = get(self.download_link, stream=True)
		except RequestException:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		r.close()
		if not r.ok:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)
		self.size = int(r.headers.get('Content-Length', -1))

		self._filename_body = filename_body
		if not custom_name:
			self._filename_body = splitext(unquote_plus(
				self.download_link.split('/')[-1].split("?")[0]
			))[0]

		self.title = basename(self._filename_body)
		self.file = self._build_filename(r)
		return

	def __extract_extension(self,
		content_type: str,
		content_disposition: str,
		url: str
	) -> str:
		"""Find the extension of the file behind the link

		Args:
			content_type (str): The value of the Content-Type header
			content_disposition (str): The value of the Content-Disposition header
			url (str): The url leading to the file

		Returns:
			str: The extension of the file, including the `.`
		"""
		match = file_extension_regex.findall(
			' '.join((
				content_disposition,
				content_type,
				url
			))
		)
		extension = ''
		if match:
			extension += '.' + match[0]

		return extension

	def _build_filename(self, r) -> str:
		"""Build the filename from the download folder, filename body and extension

		Args:
			r (Request): The request to the link

		Returns:
			str: The filename
		"""
		folder = Settings()['download_folder']
		extension = self.__extract_extension(
			r.headers.get('Content-Type', ''),
			r.headers.get('Content-Disposition', ''),
			r.url
		)
		return join(
			folder,
			'_'.join(self._filename_body.split(sep)) + extension
		)

	def run(self) -> None:
		self.state = DownloadState.DOWNLOADING_STATE
		size_downloaded = 0
		ws = WebSocket()
		ws.update_queue_status(self)

		with get(self.download_link, stream=True) as r, \
		open(self.file, 'wb') as f:

			start_time = perf_counter()
			try:
				for chunk in r.iter_content(chunk_size=download_chunk_size):
					if self.state in (DownloadState.CANCELED_STATE,
									DownloadState.SHUTDOWN_STATE):
						break

					f.write(chunk)

					# Update progress
					chunk_size = len(chunk)
					size_downloaded += chunk_size
					self.speed = round(
						chunk_size / (perf_counter() - start_time),
						2
					)
					if self.size == -1:
						# No file size so progress is amount downloaded
						self.progress = size_downloaded
					else:
						self.progress = round(
							size_downloaded / self.size * 100,
							2
						)
					start_time = perf_counter()

					ws.update_queue_status(self)

			except ChunkedEncodingError:
				self.state = DownloadState.FAILED_STATE

		return

	def stop(self,
		state: DownloadState = DownloadState.CANCELED_STATE
	) -> None:
		self.state = state
		return


class MediaFireFolderDownload(DirectDownload, BaseDownload):
	"For download a MediaFire folder (for MF file, use DirectDownload)"

	type = 'mf_folder'

	def __init__(self,
		link: str,
		filename_body: str,
		source: str,
		custom_name: bool=True
	):
		"""Setup the MF folder download

		Args:
			link (str): The folder ID.
			filename_body (str): The body of the filename to write to.
			source (str): The name of the source of the link.
			custom_name (bool, optional): If the name supplied should be used
			or the default filename.
				Defaults to True.

		Raises:
			LinkBroken: The link doesn't work
		"""
		LOGGER.debug(f'Creating download: MediaFire folder {link}, {filename_body}')

		self.id = None # type: ignore
		self.state: DownloadState = DownloadState.QUEUED_STATE

		self.progress: float = 0.0
		self.speed: float = 0.0
		self.size: int = 0
		self.download_link = link
		self.source = source
		self._filename_body = filename_body

		try:
			r = post(
				MEDIAFIRE_FOLDER_LINK,
				files={
					"keys": (None, self.download_link),
					"meta_only": (None, "no"),
					"allow_large_download": (None, "yes"),
					"response_format": (None, "json")
				},
				stream=True
			)

		except RequestException:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		r.close()
		if not r.ok:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)
		self.size = int(r.headers.get('content-length', -1))

		if custom_name:
			self.title = filename_body.rstrip('.')
		else:
			self.title = splitext(unquote_plus(
				r.headers["Content-Disposition"].split("filename*=UTF-8''")[-1]
			))[0]

		self.file = self._build_filename(r)
		return

	def run(self) -> None:
		self.state = DownloadState.DOWNLOADING_STATE
		size_downloaded = 0
		ws = WebSocket()
		ws.update_queue_status(self)

		with post(
				MEDIAFIRE_FOLDER_LINK,
				files={
					"keys": (None, self.download_link),
					"meta_only": (None, "no"),
					"allow_large_download": (None, "yes"),
					"response_format": (None, "json")
				},
				stream=True
		) as r, \
		open(self.file, 'wb') as f:

			start_time = perf_counter()
			try:
				for chunk in r.iter_content(chunk_size=download_chunk_size):
					if self.state in (DownloadState.CANCELED_STATE,
									DownloadState.SHUTDOWN_STATE):
						break

					f.write(chunk)

					# Update progress
					chunk_size = len(chunk)
					size_downloaded += chunk_size
					self.speed = round(
						chunk_size / (perf_counter() - start_time),
						2
					)
					if self.size == -1:
						# No file size so progress is amount downloaded
						self.progress = size_downloaded
					else:
						self.progress = round(
							size_downloaded / self.size * 100,
							2
						)
					start_time = perf_counter()

					ws.update_queue_status(self)

			except ChunkedEncodingError:
				self.state = DownloadState.FAILED_STATE

		return


class MegaDownload(BaseDownload):
	"""For downloading a file via Mega
	"""

	type = 'mega'

	@property
	def progress(self) -> float:
		return self._mega.progress

	@property
	def speed(self) -> float:
		return self._mega.speed

	@property
	def size(self) -> int:
		return self._mega.size

	def __init__(self,
		link: str,
		filename_body: str,
		source: str='mega',
		custom_name: bool=True
	):
		"""Setup the mega download

		Args:
			link (str): The mega link.

			filename_body (str): The body of the filename to write to.

			source (str, optional): The name of the source of the link.
				Defaults to 'mega'.

			custom_name (bool, optional): If the name supplied should be used
			or the default filename.
				Defaults to True.

		Raises:
			LinkBroken: The link doesn't work
		"""
		LOGGER.debug(f'Creating mega download: {link}, {filename_body}')
		super().__init__()
		self.download_link = link
		self.source = source

		cred = credentials.get_one_from_source('mega')
		try:
			self._mega = Mega(link, cred['email'], cred['password'])
		except RequestError:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		self._filename_body = filename_body
		if not custom_name:
			self._filename_body = splitext(self._mega.mega_filename)[0]

		self.title = basename(self._filename_body)
		self.file = self.__build_filename()
		return

	def __extract_extension(self) -> str:
		"""Find the extension of the file behind the link

		Returns:
			str: The extension of the file, including the `.`
		"""
		return splitext(self._mega.mega_filename)[1]

	def __build_filename(self) -> str:
		"""Build the filename from the download folder, filename body
		and extension

		Returns:
			str: The filename
		"""
		folder = Settings()['download_folder']
		extension = self.__extract_extension()
		return join(
			folder,
			'_'.join(self._filename_body.split(sep)) + extension
		)

	def run(self) -> None:
		"""
		Start the download

		Raises:
			DownloadLimitReached: The Mega download limit is reached mid-download
		"""
		self.state = DownloadState.DOWNLOADING_STATE
		ws = WebSocket()
		self._mega.download_url(
			self.file,
			lambda: ws.update_queue_status(self)
		)
		return

	def stop(self,
		state: DownloadState = DownloadState.CANCELED_STATE
	) -> None:
		self.state = state
		self._mega.downloading = False
		return
