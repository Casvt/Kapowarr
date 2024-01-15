#-*- coding: utf-8 -*-

from re import IGNORECASE, compile
from typing import Union

from requests import Session, post
from requests.exceptions import RequestException

from backend.download_general import BaseTorrentClient
from backend.enums import DownloadState
from backend.settings import private_settings

filename_magnet_link = compile(r'(?<=&dn=).*?(?=&)', IGNORECASE)
hash_magnet_link = compile(r'(?<=urn:btih:)\w+?(?=&)', IGNORECASE)

class qBittorrent(BaseTorrentClient):
	_tokens = ('title', 'base_url', 'username', 'password')

	def __init__(self, id: int) -> None:
		super().__init__(id)

		self.ssn = Session()

		if self.username and self.password:
			data = {
				'username': self.username,
				'password': self.password
			}
		else:
			data = {}

		self.ssn.post(
			f'{self.base_url}/api/v2/auth/login',
			data=data
		)
		
		self.torrent_found = False

		return

	def add_torrent(self,
		magnet_link: str,
		target_folder: str,
		torrent_name: Union[str, None]
	) -> int:
		if torrent_name is not None:
			magnet_link = filename_magnet_link.sub(torrent_name, magnet_link)
			
		files = {
			'urls': (None, magnet_link),
			'savepath': (None, target_folder),
			'category': (None, private_settings['torrent_tag'])
		}
			
		self.ssn.post(
			f'{self.base_url}/api/v2/torrents/add',
			files=files
		)
		
		return hash_magnet_link.search(magnet_link).group(0)

	def get_torrent_status(self, torrent_id: int) -> Union[dict, None]:
		r = self.ssn.get(
			f'{self.base_url}/api/v2/torrents/properties',
			params={'hash': torrent_id}
		)
		if r.status_code == 404:
			return None if self.torrent_found else {}

		self.torrent_found = True
		result = r.json()

		if result['pieces_have'] <= 0:
			state = DownloadState.QUEUED_STATE

		elif result['completion_date'] == -1:
			state = DownloadState.DOWNLOADING_STATE

		elif result['eta'] != 8640000:
			state = DownloadState.SEEDING_STATE
		
		else:
			state = DownloadState.IMPORTING_STATE

		return {
			'size': result['total_size'],
			'progress': round(
				(result['total_downloaded'] - result['total_wasted'])
				/
				result['total_size'] * 100,

				2
			),
			'speed': result['dl_speed'],
			'state': state
		}

	def delete_torrent(self, torrent_id: int, delete_files: bool) -> None:
		self.ssn.post(
			f'{self.base_url}/api/v2/torrents/delete',
			data={
				'hashes': torrent_id,
				'deleteFiles': delete_files
			}
		)
		return

	@staticmethod
	def test(
		base_url: str,
		username: Union[str, None] = None,
		password: Union[str, None] = None,
		api_token: Union[str, None] = None
	) -> bool:
		try:
			if username and password:
				params = {
					'username': username,
					'password': password
				}
			else:
				params = {}

			auth_request = post(
				f'{base_url}/api/v2/auth/login',
				data=params
			)
			if auth_request.status_code == 404:
				return False
			cookie = auth_request.headers.get('set-cookie')
			
			return cookie is not None
		
		except RequestException:
			return False
