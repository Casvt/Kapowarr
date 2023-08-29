#-*- coding: utf-8 -*-

"""Downloading from GetComics
"""

import logging
from abc import ABC, abstractmethod
from os.path import basename, splitext, join
from re import IGNORECASE, compile
from time import perf_counter
from urllib.parse import unquote_plus

from requests import get
from requests.exceptions import ChunkedEncodingError

from backend.credentials import Credentials
from backend.custom_exceptions import LinkBroken
from backend.settings import blocklist_reasons, Settings

from .lib.mega import Mega, RequestError, sids

file_extension_regex = compile(r'(?<=\.)[\w\d]{2,4}(?=$|;|\s)|(?<=\/)[\w\d]{2,4}(?=$|;|\s)', IGNORECASE)
credentials = Credentials(sids)
download_chunk_size = 4194304 # 4MB Chunks

class DownloadStates:
	QUEUED_STATE = 'queued'
	DOWNLOADING_STATE = 'downloading'
	IMPORTING_STATE = 'importing'
	FAILED_STATE = 'failed'
	CANCELED_STATE = 'canceled'

class Download(ABC):
	# This block is assigned after initialisation of the object
	id: int
	db_id: int
	volume_id: int
	issue_id: int
	page_link: str

	source: str
	download_link: str

	file: str
	title: str
	size: int

	state: str
	progress: float
	speed: float

	@abstractmethod
	def run(self) -> None:
		return
		
	@abstractmethod
	def stop(self) -> None:
		return

	@abstractmethod
	def todict(self) -> dict:
		return

class BaseDownload(Download):
	def __init__(self):
		self.state: str = DownloadStates.QUEUED_STATE

	def todict(self) -> dict:
		return {
			'id': self.id,
			'volume_id': self.volume_id,
			'issue_id': self.issue_id,

			'page_link': self.page_link,
			'source': self.source,
			'download_link': self.download_link,

			'file': self.file,
			'title': self.title,
			'size': self.size,

			'status': self.state,
			'progress': self.progress,
			'speed': self.speed,
		}
	
	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}, {self.download_link}>'

class DirectDownload(BaseDownload):
	"""For downloading a file directly from a link
	"""	
	def __init__(self, link: str, filename_body: str, source: str, custom_name: bool=True):
		"""Setup the direct download

		Args:
			link (str): The link (that leads to a file) that should be used
			filename_body (str): The body of the filename to write to
			source (str): The name of the source of the link
			custom_name (bool, optional): If the name supplied should be used or the default filename. Defaults to True.

		Raises:
			LinkBroken: The link doesn't work
		"""
		logging.debug(f'Creating download: {link}, {filename_body}')
		super().__init__()
		self.progress: float = 0.0
		self.speed: float = 0.0
		self.download_link = link
		self.source = source

		self.size: int = 0
		r = get(self.download_link, stream=True)
		r.close()
		if not r.ok:
			raise LinkBroken(1, blocklist_reasons[1])
		if custom_name:
			self.__filename_body = filename_body.rstrip('.')
		else:
			self.__filename_body = splitext(unquote_plus(self.download_link.split('/')[-1]))[0]

		self.file = self.__build_filename(r)
		self.title = splitext(basename(self.file))[0]
		self.size = int(r.headers.get('content-length',-1))

	def __extract_extension(self, content_type: str, content_disposition: str, url: str) -> str:
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
				content_type,
				content_disposition,
				url
			))
		)
		if match:
			extension = '.' + match[0]
		else:
			extension = ''

		return extension

	def __build_filename(self, r) -> str:
		"""Build the filename from the download folder, filename body and extension

		Args:
			r (_type_): The request to the link

		Returns:
			str: The filename
		"""		
		folder = Settings().get_settings()['download_folder']
		extension = self.__extract_extension(
			r.headers.get('Content-Type', ''),
			r.headers.get('Content-Disposition', ''),
			r.url
		)
		return join(folder, self.__filename_body + extension)

	def run(self) -> None:
		"""Start the download
		"""		
		self.state = DownloadStates.DOWNLOADING_STATE
		size_downloaded = 0

		with get(self.download_link, stream=True) as r:
			with open(self.file, 'wb') as f:
				start_time = perf_counter()
				try:
					for chunk in r.iter_content(chunk_size=download_chunk_size):
						if self.state == DownloadStates.CANCELED_STATE:
							break

						f.write(chunk)

						# Update progress
						chunk_size = len(chunk)
						size_downloaded += chunk_size
						self.speed = round(chunk_size / (perf_counter() - start_time), 2)
						if self.size == -1:
							# Total size of file is not given so set progress to amount downloaded
							self.progress = size_downloaded
						else:
							# Total size of file is given so calculate progress and speed
							self.progress = round(size_downloaded / self.size * 100, 2)
						start_time = perf_counter()

				except ChunkedEncodingError:
					self.state = DownloadStates.FAILED_STATE

		return

	def stop(self) -> None:
		"""Interrupt the download
		"""
		self.state = DownloadStates.CANCELED_STATE
		return

class MegaDownload(BaseDownload):
	@property
	def progress(self) -> float:
		return self._mega.progress

	@property
	def speed(self) -> float:
		return self._mega.speed

	@property
	def size(self) -> int:
		return self._mega.size

	def __init__(self, link: str, filename_body: str, source: str='mega', custom_name: bool=True):
		"""Setup the mega download

		Args:
			link (str): The mega link
			filename_body (str): The body of the filename to write to
			source (str, optional): The name of the source of the link. Defaults to 'mega'.
			custom_name (bool, optional): If the name supplied should be used or the default filename. Defaults to True.

		Raises:
			LinkBroken: The link doesn't work
		"""
		logging.debug(f'Creating mega download: {link}, {filename_body}')
		super().__init__()
		self.download_link = link
		self.source = source

		self.__filename_body = filename_body.rstrip('.')
		cred = credentials.get_one_from_source('mega')
		try:
			self._mega = Mega(link, cred['email'], cred['password'])
		except RequestError:
			raise LinkBroken(1, blocklist_reasons[1])

		if not custom_name:
			self.__filename_body = splitext(self._mega.mega_filename)[0]

		self.file = self.__build_filename()
		self.title = splitext(basename(self.file))[0]
		
	def __extract_extension(self) -> str:
		"""Find the extension of the file behind the link

		Returns:
			str: The extension of the file, including the `.`
		"""
		return splitext(self._mega.mega_filename)[1]

	def __build_filename(self) -> str:
		"""Build the filename from the download folder, filename body and extension

		Returns:
			str: The filename
		"""
		folder = Settings().get_settings()['download_folder']
		extension = self.__extract_extension()
		return join(folder, self.__filename_body + extension)

	def run(self) -> None:
		"""
		Start the download
		
		Raises:
			DownloadLimitReached: The Mega download limit is reached mid-download
		"""		
		self.state = DownloadStates.DOWNLOADING_STATE
		self._mega.download_url(self.file)

	def stop(self) -> None:
		"""Interrupt the download
		"""		
		self.state = DownloadStates.CANCELED_STATE
		self._mega.downloading = False
