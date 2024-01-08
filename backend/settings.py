#-*- coding: utf-8 -*-

"""Settings-like data, interacting with the settings and service preference
"""

import logging
from json import dumps, loads
from os import urandom
from os.path import isdir, join
from typing import Any

from backend.custom_exceptions import (FolderNotFound, InvalidSettingKey,
                                       InvalidSettingModification,
                                       InvalidSettingValue)
from backend.db import __DATABASE_FILEPATH__, __DATABASE_VERSION__, get_db
from backend.enums import SeedingHandling
from backend.files import folder_path
from backend.helpers import (CommaList, Singleton, first_of_column,
                             get_python_version)
from backend.logging import log_levels, set_log_level

supported_source_strings = (('mega',),
							('mediafire',),
							('getcomics', 'download now', 'main server', 'mirror download', 'link 1', 'link 2'),
							('getcomics (torrent)', 'torrent'))

default_settings = {
	'database_version': __DATABASE_VERSION__,
	'host': '0.0.0.0',
	'port': 5656,
	'url_base': '',
	'api_key': None,
	'comicvine_api_key': '',
	'auth_password': '',
	'log_level': 'info',

	'volume_folder_naming': join('{series_name}', 'Volume {volume_number} ({year})'),
	'file_naming': '{series_name} ({year}) Volume {volume_number} Issue {issue_number}',
	'file_naming_tpb': '{series_name} ({year}) Volume {volume_number} TPB',
	'file_naming_empty': '{series_name} ({year}) Volume {volume_number} Issue {issue_number}',
	'volume_as_empty': False,
	'volume_padding': 2,
	'issue_padding': 3,
	'rename_downloaded_files': True,

	'service_preference': str(CommaList(
		first_of_column(supported_source_strings)
	)),
	'download_folder': folder_path('temp_downloads'),
	'seeding_handling': SeedingHandling.COPY.value,
	'delete_completed_torrents': True,

	'convert': False,
	'extract_issue_ranges': False,
	'format_preference': ''
}

private_settings = {
	'comicvine_url': 'https://comicvine.gamespot.com',
	'comicvine_api_url': 'https://comicvine.gamespot.com/api',
	'getcomics_url': 'https://getcomics.org',
	'hosting_threads': 10,
	'version': 'v1.0.0-beta-4',
	'python_version': get_python_version(),
	'torrent_update_interval': 5, # Seconds
	'torrent_tag': 'kapowarr'
}

about_data = {
	'version': private_settings['version'],
	'python_version': private_settings['python_version'],
	'database_version': __DATABASE_VERSION__,
	'database_location': folder_path(*__DATABASE_FILEPATH__),
	'data_folder': folder_path()
}

task_intervals = {
	# If there are tasks that should be run at the same time,
	# but per se after each other, put them in that order in the dict.
	'update_all': 3600, # every hour
	'search_all': 86400 # every day
}

credential_sources = ('mega',)

def update_manifest(url_base: str) -> None:
	with open(folder_path('frontend', 'static', 'json', 'manifest.json'), 'r+') as f:
		manifest = loads(f.read())
		manifest['start_url'] = url_base + '/'
		manifest['icons'][0]['src'] = f'{url_base}/static/img/favicon.svg'
		f.seek(0)
		f.write(dumps(manifest, indent=4))
	return

class Settings(metaclass=Singleton):
	"Note: Is singleton"
	
	def __init__(self) -> None:
		cursor = get_db()

		cursor.executemany(
			"""
			INSERT OR IGNORE INTO config
			VALUES (?,?);
			""",
			default_settings.items()
		).connection.commit()

		settings = dict(cursor.execute(
			"SELECT key, value FROM config;"
		))

		bool_values = ('rename_downloaded_files', 'volume_as_empty',
					'convert', 'extract_issue_ranges',
					'delete_completed_torrents')
		for bv in bool_values:
			settings[bv] = settings[bv] == 1
		
		settings['format_preference'] = CommaList(settings['format_preference'])
		settings['service_preference'] = CommaList(settings['service_preference'])

		self.settings = settings
		return

	def __check_value(self, key: str, value: Any) -> Any:
		"""Check if value of setting is allowed and covert if needed

		Args:
			key (str): Key of setting
			value (Any): Value of setting

		Raises:
			InvalidSettingValue: Value is not allowed
			InvalidSettingModification: Key can not be modified this way
			FolderNotFound: Folder not found

		Returns:
			Any: (Converted) Setting value
		"""		
		if key == 'port' and not value.isdigit():
			raise InvalidSettingValue(key, value)

		elif key == 'api_key':
			raise InvalidSettingModification(key, 'POST /settings/api_key')

		elif key == 'comicvine_api_key':
			from backend.comicvine import ComicVine
			value = value.strip()
			if not ComicVine(value).test_token():
				raise InvalidSettingValue(key, value)

		elif key == 'download_folder' and not isdir(value):
			raise FolderNotFound

		elif key in ('rename_downloaded_files', 'volumes_as_empty',
					'convert', 'extract_issue_ranges',
					'delete_completed_torrents'):
			if not isinstance(value, bool):
				raise InvalidSettingValue(key, value)

		elif key in ('volume_folder_naming','file_naming',
					'file_naming_tpb','file_naming_empty'):
			from backend.naming import check_format

			check_format(value, key)

		elif key == 'log_level' and not value in log_levels:
			raise InvalidSettingValue(key, value)

		elif key == 'url_base':
			if value:
				value = ('/' + value.lstrip('/')).rstrip('/')

		elif key == 'volume_padding':
			try:
				if not 1 <= value <= 3:
					raise InvalidSettingValue(key, value)
			except TypeError:
				raise InvalidSettingValue(key, value)

		elif key == 'issue_padding':
			try:
				if not 1 <= value <= 4:
					raise InvalidSettingValue(key, value)
			except TypeError:
				raise InvalidSettingValue(key, value)

		elif key in ('format_preference', 'service_preference'):
			if key == 'format_preference':
				from backend.conversion import get_available_formats
				available = get_available_formats()
			elif key == 'service_preference':
				available = first_of_column(supported_source_strings)
			
			if not isinstance(value, list):
				raise InvalidSettingValue(key, value)

			for entry in value:
				if not isinstance(entry, str):
					raise InvalidSettingValue(key, value)
				if not entry in available:
					raise InvalidSettingValue(key, value)

			value = CommaList(value)

		elif key == 'seeding_handling':
			try:
				SeedingHandling(value)
			except ValueError:
				raise InvalidSettingValue(key, value)

		return value

	def __getitem__(self, __name: str) -> Any:
		return self.settings[__name]

	def get_all(self) -> dict:
		"""Get all settings

		Returns:
			dict: The settings
		"""
		return self.settings

	def __setitem__(self, __name: str, __value: Any) -> None:
		name = __name
		value = __value

		logging.info(f'Changing setting: {name}->{value}')

		if not name in default_settings:
			raise InvalidSettingKey(name)

		value = self.__check_value(name, value)
		
		self.settings[name] = value
		
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = ?;",
			(value, name)
		)
		
		if name == 'log_level':
			set_log_level(value)

		elif name == 'url_base':
			update_manifest(value)
		
		return

	def update(self, changes: dict) -> None:
		"""dict-like update method for the settings
		but with checking of the values.

		Args:
			changes (dict): The keys and their new values

		Raises:
			InvalidSettingKey: Key is not allowed
			InvalidSettingValue: Value of the key is not allowed
			InvalidSettingModification: Key can not be modified this way
			FolderNotFound: Folder not found
		"""		
		for key, value in changes.items():
			if not key in default_settings:
				raise InvalidSettingKey(key)
			
			value = self.__check_value(key, value)
			
			changes[key] = value

		self.settings.update(changes)
		get_db().executemany(
			"UPDATE config SET value = ? WHERE key = ?;",
			((value, key) for key, value in changes.items())
		)
		
		if 'log_level' in changes:
			set_log_level(changes['log_level'])
		if 'url_base' in changes:
			update_manifest(changes['url_base'])

		logging.info(f'Settings changed: {changes}')

		return

	def reset(self, key: str) -> None:
		"""Reset the value of the key to the default value

		Args:
			key (str): The key of which to reset the value

		Raises:
			InvalidSettingKey: The key is not valid
		"""
		logging.debug(f'Setting reset: {key}')

		if not key in default_settings:
			raise InvalidSettingKey(key)

		self.settings[key] = default_settings[key]
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = ?",
			(default_settings[key], key)
		)

		if key == 'log_level':
			set_log_level(default_settings[key])

		elif key == 'url_base':
			update_manifest(default_settings[key])

		logging.info(f'Setting reset: {key}->{default_settings[key]}')
		return

	def generate_api_key(self) -> None:
		"""Generate a new api key
		"""
		logging.debug('Generating new api key')
		api_key = urandom(16).hex()
		self.settings['api_key'] = api_key
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = 'api_key';",
			(api_key,)
		)
		logging.info(f'Setting api key regenerated: {api_key}')

		return

	def _save_to_database(self) -> None:
		"""Commit database to save changes
		"""
		get_db().connection.commit()
		return
