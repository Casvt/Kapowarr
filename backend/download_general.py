#-*- coding: utf-8 -*-

"""
General classes (ABC's, base classes) regarding downloading
"""

from abc import ABC, abstractmethod
from typing import Tuple, Union

from backend.custom_exceptions import (InvalidKeyValue, KeyNotFound,
                                       TorrentClientDownloading,
                                       TorrentClientNotWorking)
from backend.db import get_db
from backend.enums import DownloadState


class Download(ABC):
	# This block is assigned after initialisation of the object
	id: Union[int, None]
	volume_id: Union[int, None]
	issue_id: Union[int, None]
	page_link: Union[str, None]

	_filename_body: str
	source: str
	download_link: str
	type: str

	file: str
	title: str
	size: int

	state: DownloadState
	progress: float
	speed: float

	@abstractmethod
	def __init__(
		self,
		link: str,
		filename_body: str,
		source: str,
		custom_name: bool=True
	) -> None:
		"""Create the download instance

		Args:
			link (str): The link to the download
				(could be direct download link, mega link or magnet link)

			filename_body (str): The body of the file to download to

			source (str): The source of the download

			custom_name (bool, optional): Whether or not to use the filename body
			or to use the default name of the download. Defaults to True.
		"""
		return

	@abstractmethod
	def run(self) -> None:
		"""Start the download
		"""
		return
		
	@abstractmethod
	def stop(
		self, 
		state: DownloadState = DownloadState.CANCELED_STATE
	) -> None:
		"""Interrupt the download

		Args:
			state (DownloadState, optional): The state to set for the download.
				Defaults to DownloadState.CANCELED_STATE.
		"""
		return

	@abstractmethod
	def todict(self) -> dict:
		"""Get a dict representing the download.

		Returns:
			dict: The dict with all information.
		"""
		return

class TorrentClient(ABC):
	id: int
	type: str
	title: str
	base_url: str
	username: Union[str, None]
	password: Union[str, None]
	api_token: Union[str, None]
	
	_tokens: Tuple[str] = ('title', 'base_url')
	"""The keys the client needs or could need for operation 
	(mostly whether it's username + password or api_token)"""

	@abstractmethod
	def __init__(self, id: int) -> None:
		"""Create a connection with a torrent client

		Args:
			id (int): The id of the torrent client
		"""
		return

	@abstractmethod
	def todict(self) -> dict:
		"""Get info about torrent client in a dict

		Returns:
			dict: The info about the torrent client
		"""
		return

	@abstractmethod
	def edit(self, edits: dict) -> dict:
		"""Edit the torrent client

		Args:
			edits (dict): The keys and their new values for
			the torrent client settings

		Raises:
			TorrentClientDownloading: The is a download in the queue
			using the client

		Returns:
			dict: The new info of the torrent client
		"""
		return

	@abstractmethod
	def delete(self) -> None:
		"""Delete the torrent client
		
		Raises:
			TorrentClientDownloading: There is a download in the queue
			using the client
		"""
		return

	@abstractmethod
	def add_torrent(self,
		magnet_link: str,
		target_folder: str,
		torrent_name: Union[str, None]
	) -> int:
		"""Add a torrent to the client for downloading

		Args:
			magnet_link (str): The magnet link of the torrent to download
			target_folder (str): The folder to download in
			torrent_name (Union[str, None]): The name of the torrent in the client
			Set to `None` to keep original name.

		Returns:
			int: The id of the entry in the download client
		"""
		return
	
	@abstractmethod
	def get_torrent_status(self, torrent_id: int) -> dict:
		"""Get the status of the torrent in a dict

		Args:
			torrent_id (int): The id of the torrent to get status of

		Returns:
			dict: The status of the torrent,
			or empty dict if torrent is not found.
		"""
		return

	@abstractmethod
	def delete_torrent(self, torrent_id: int, delete_files: bool) -> None:
		"""Remove the torrent from the client

		Args:
			torrent_id (int): The id of the torrent to delete
			delete_files (bool): Delete the downloaded files
		"""
		return

	@staticmethod
	@abstractmethod
	def test(
		base_url: str,
		username: Union[str, None],
		password: Union[str, None],
		api_token: Union[str, None]
	) -> bool:
		"""Check if a torrent client is working

		Args:
			base_url (str): The base url on which the client is running.
			username (Union[str, None]): The username to access the client, if set.
			password (Union[str, None]): The password to access the client, if set.
			api_token (Union[str, None]): The api token to access the client, if set.

		Returns:
			bool: Whether or not the test succeeded
		"""
		return

class BaseTorrentClient(TorrentClient):
	def __init__(self, id: int) -> None:
		self.id = id
		data = get_db(dict).execute("""
			SELECT
				type, title,
				base_url,
				username, password,
				api_token
			FROM torrent_clients
			WHERE id = ?
			LIMIT 1;
			""",
			(id,)
		).fetchone()
		self.type = data['type']
		self.title = data['title']
		self.base_url = data['base_url']
		self.username = data['username']
		self.password = data['password']
		self.api_token = data['api_token']
		return
	
	def todict(self) -> dict:
		return {
			'id': self.id,
			'type': self.type,
			'title': self.title,
			'base_url': self.base_url,
			'username': self.username,
			'password': self.password,
			'api_token': self.api_token
		}
	
	def edit(self, edits: dict) -> dict:
		cursor = get_db()
		if cursor.execute(
			"SELECT 1 FROM download_queue WHERE torrent_client_id = ? LIMIT 1;",
			(self.id,)
		).fetchone() is not None:
			raise TorrentClientDownloading

		from backend.download_torrent_clients import client_types
		data = {}
		for key in ('title', 'base_url', 'username', 'password', 'api_token'):
			if key in self._tokens and not key in edits:
				raise KeyNotFound(key)
			if key in ('title', 'base_url') and edits[key] is None:
				raise InvalidKeyValue(key, None)
			data[key] = edits.get(key) if key in self._tokens else None

		if data['username'] is not None and data['password'] is None:
			raise InvalidKeyValue('password', data['password'])

		data['base_url'] = data['base_url'].rstrip('/')

		ClientClass = client_types[self.type]
		test_result = ClientClass.test(
			data['base_url'],
			data['username'],
			data['password'],
			data['api_token']
		)
		if not test_result:
			raise TorrentClientNotWorking

		cursor.execute("""
			UPDATE torrent_clients SET
				title = ?,
				base_url = ?,
				username = ?,
				password = ?,
				api_token = ?
			WHERE id = ?;
			""",
			(data['title'], data['base_url'],
			data['username'], data['password'], data['api_token'],
			self.id)
		)
		return ClientClass(self.id).todict()

	def delete(self) -> None:
		cursor = get_db()
		if cursor.execute(
			"SELECT 1 FROM download_queue WHERE torrent_client_id = ? LIMIT 1;",
			(self.id,)
		).fetchone() is not None:
			raise TorrentClientDownloading(self.id)

		cursor.execute(
			"DELETE FROM torrent_clients WHERE id = ?;",
			(self.id,)
		)

		return None

	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}; ID {self.id}; {id(self)}>'
