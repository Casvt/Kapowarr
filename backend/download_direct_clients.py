#-*- coding: utf-8 -*-

"""
Clients for downloading from a direct URL and Mega.
Used when downloading from GC.
"""

from __future__ import annotations

from os.path import basename, join, sep, splitext
from re import IGNORECASE, compile
from time import perf_counter
from typing import TYPE_CHECKING
from urllib.parse import unquote_plus

from bs4 import BeautifulSoup, Tag
from requests import RequestException, get, post
from requests.exceptions import ChunkedEncodingError

from backend.credentials import Credentials
from backend.custom_exceptions import LinkBroken
from backend.download_general import Download
from backend.enums import BlocklistReason, DownloadState
from backend.logging import LOGGER
from backend.server import WebSocket
from backend.settings import Settings

from .lib.mega import Mega, RequestError, sids

if TYPE_CHECKING:
	from requests import Response

file_extension_regex = compile(r'(?<=\.|\/)[\w\d]{2,4}(?=$|;|\s|\")', IGNORECASE)
extract_mediafire_regex = compile(
	r'window.location.href\s?=\s?\'https://download\d+\.mediafire.com/.*?(?=\')',
	IGNORECASE
)
credentials = Credentials(sids)
DOWNLOAD_CHUNK_SIZE = 4194304 # 4MB Chunks
MEDIAFIRE_FOLDER_LINK = "https://www.mediafire.com/api/1.5/file/zip.php"
WETRANSFER_API_LINK = "https://wetransfer.com/api/v4/transfers/{transfer_id}/download"
PIXELDRAIN_API_LINK = "https://pixeldrain.com/api/file/{download_id}"


class BaseDirectDownload(Download):
	def __init__(self,
		download_link: str,
		filename_body: str,
		source: str,
		custom_name: bool=True
	):
		LOGGER.debug(f'Creating download: {download_link}, {filename_body}')
		self.id = None # type: ignore
		self.state: DownloadState = DownloadState.QUEUED_STATE
		self.progress: float = 0.0
		self.speed: float = 0.0
		self.size: int = 0
		self.download_link = download_link
		self.source = source

		try:
			self.pure_link = self._convert_to_pure_link()
		except RequestException:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		try:
			r = self._fetch_pure_link()
		except RequestException:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		r.close()
		if not r.ok:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)
		self.size = int(r.headers.get('Content-Length', -1))

		self._filename_body = filename_body
		if not custom_name:
			self._filename_body = self._extract_default_filename_body(r)

		self.title = basename(self._filename_body)
		self.file = self._build_filename(r)
		return

	def _convert_to_pure_link(self) -> str:
		return self.download_link

	def _fetch_pure_link(self) -> Response:
		return get(self.pure_link, stream=True)

	def _extract_default_filename_body(self, r: Response) -> str:
		return splitext(unquote_plus(
			self.pure_link.split('/')[-1].split("?")[0]
		))[0]

	def _build_filename(self, r: Response) -> str:
		folder = Settings()['download_folder']
		extension = self._extract_extension(r)
		return join(
			folder,
			'_'.join(self._filename_body.split(sep)) + extension
		)

	def _extract_extension(self, r: Response) -> str:
		match = file_extension_regex.findall(
			' '.join((
				r.headers.get('Content-Disposition', ''),
				r.headers.get('Content-Type', ''),
				r.url
			))
		)
		extension = ''
		if match:
			extension += '.' + match[0]

		return extension

	def run(self) -> None:
		self.state = DownloadState.DOWNLOADING_STATE
		size_downloaded = 0
		ws = WebSocket()
		ws.update_queue_status(self)

		with self._fetch_pure_link() as r, \
		open(self.file, 'wb') as f:

			start_time = perf_counter()
			try:
				for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
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

	def todict(self) -> dict:
		return {
			'id': self.id,
			'volume_id': self.volume_id,
			'issue_id': self.issue_id,

			'web_link': self.web_link,
			'web_title': self.web_title,
			'web_sub_title': self.web_sub_title,
			'download_link': self.download_link,
			'pure_link': self.pure_link,

			'source': self.source,
			'type': self.type,

			'file': self.file,
			'title': self.title,

			'size': self.size,
			'status': self.state.value,
			'progress': self.progress,
			'speed': self.speed
		}

	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}, {self.download_link}, {self.file}>'


class DirectDownload(BaseDirectDownload):
	"For downloading a file directly from a link"

	type = 'direct'


class MediaFireDownload(BaseDirectDownload):
	"For downloading a MediaFire file"

	type = 'mf'

	def _convert_to_pure_link(self) -> str:
		r = get(self.download_link, headers={'User-Agent': 'Kapowarr'}, stream=True)
		result = extract_mediafire_regex.search(r.text)
		if result:
			return result.group(0).split("'")[-1]

		soup = BeautifulSoup(r.text, 'html.parser')
		button = soup.find('a', {'id': 'downloadButton'})
		if isinstance(button, Tag):
			return button['href']

		# Link is not broken and not a folder
		# but we still can't find the download button...
		raise LinkBroken(BlocklistReason.LINK_BROKEN)


class MediaFireFolderDownload(BaseDirectDownload):
	"For downloading a MediaFire folder (for MF file, use MediaFireDownload)"

	type = 'mf_folder'

	def _convert_to_pure_link(self) -> str:
		return self.download_link.split("/folder/")[1].split("/")[0]

	def _fetch_pure_link(self) -> Response:
		return post(
			MEDIAFIRE_FOLDER_LINK,
			files={
				"keys": (None, self.pure_link),
				"meta_only": (None, "no"),
				"allow_large_download": (None, "yes"),
				"response_format": (None, "json")
			},
			stream=True
		)

	def _extract_default_filename_body(self, r: Response) -> str:
		return splitext(unquote_plus(
			r.headers["Content-Disposition"].split("filename*=UTF-8''")[-1]
		))[0]


class WeTransferDownload(BaseDirectDownload):
	"For downloading a file or folder from WeTransfer"

	type = 'wt'

	def _convert_to_pure_link(self) -> str:
		transfer_id, security_hash = self.download_link.split("/")[-2:]
		r = post(
			WETRANSFER_API_LINK.format(transfer_id=transfer_id),
			json={
				"intent": "entire_transfer",
				"security_hash": security_hash
			},
			headers={
				"User-Agent": "Kapowarr",
				"x-requested-with": "XMLHttpRequest"
			}
		)
		if not r.ok:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		direct_link = r.json().get("direct_link")

		if not direct_link:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		return direct_link


class PixelDrainDownload(BaseDirectDownload):
	"For downloading a file from PixelDrain"

	type = 'pd'

	def _convert_to_pure_link(self) -> str:
		download_id = self.download_link.rstrip("/").split("/")[-1]
		return PIXELDRAIN_API_LINK.format(download_id=download_id)


class MegaDownload(BaseDirectDownload):
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
		download_link: str,
		filename_body: str,
		source: str = "mega",
		custom_name: bool = True
	):
		LOGGER.debug(f'Creating mega download: {download_link}, {filename_body}')
		self.id = None # type: ignore
		self.state: DownloadState = DownloadState.QUEUED_STATE
		self.download_link = download_link
		self.pure_link = download_link
		self.source = source

		cred = credentials.get_one_from_source('mega')
		try:
			self._mega = Mega(download_link, cred['email'], cred['password'])
		except RequestError:
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		self._filename_body = filename_body
		if not custom_name:
			self._filename_body = splitext(self._mega.mega_filename)[0]

		self.title = basename(self._filename_body)
		self.file = self._build_filename(None) # type: ignore
		return

	def _extract_extension(self, r: Response) -> str:
		return splitext(self._mega.mega_filename)[1]

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
		super().stop(state)
		self._mega.downloading = False
		return
