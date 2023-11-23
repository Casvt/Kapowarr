#-*- coding: utf-8 -*-

from re import IGNORECASE, compile
from typing import Union

from requests import Session, get
from requests.exceptions import RequestException

from backend.download_general import BaseTorrentClient, DownloadStates
from backend.settings import private_settings

filename_magnet_link = compile(r'(?<=&dn=).*?(?=&)', IGNORECASE)
hash_magnet_link = compile(r'(?<=urn:btih:)\w+?(?=&)', IGNORECASE)

class qBittorrent(BaseTorrentClient):
	_tokens = ('title', 'base_url', 'username', 'password')

	def __init__(self, id: int) -> None:
		super().__init__(id)

		self.ssn = Session()

		if self.username and self.password:
			params = {
				'username': self.username,
				'password': self.password
			}
		else:
			params = {}

		self.ssn.get(
			f'{self.base_url}/api/v2/auth/login',
			params=params
		)

		return

	def add_torrent(self,
		magnet_link: str,
		target_folder: str,
		torrent_name: Union[str, None]
	) -> int:
		if torrent_name is not None:
			magnet_link = filename_magnet_link.sub(torrent_name, magnet_link)
			
		params = {
			'urls': magnet_link,
			'savepath': target_folder,
			'category': private_settings['torrent_tag']
		}
			
		self.ssn.get(
			f'{self.base_url}/api/v2/torrents/add',
			params=params
		)
		
		return hash_magnet_link.search(magnet_link).group(0)

	def get_torrent_status(self, torrent_id: int) -> dict:
		result = self.ssn.get(
			f'{self.base_url}/api/v2/torrents/properties',
			params={'hash': torrent_id}
		).json()

		if result['pieces_have'] <= 0:
			state = DownloadStates.QUEUED_STATE

		elif result['completion_date'] == -1:
			state = DownloadStates.DOWNLOADING_STATE

		elif result['eta'] != 8640000:
			state = DownloadStates.SEEDING_STATE
		
		else:
			state = DownloadStates.IMPORTING_STATE

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
		self.ssn.get(
			f'{self.base_url}/api/v2/torrents/delete',
			params={
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

			cookie = get(
				f'{base_url}/api/v2/auth/login',
				params=params
			).headers.get('set-cookie')
			
			return cookie is not None
		
		except RequestException:
			return False
