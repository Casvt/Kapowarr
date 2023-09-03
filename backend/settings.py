#-*- coding: utf-8 -*-

"""Settings-like data, interacting with the settings and service preference
"""

import logging
from json import dumps, loads
from os import urandom
from os.path import isdir
from os.path import sep as path_sep
from sys import version_info
from typing import List

from backend.custom_exceptions import (FolderNotFound, InvalidSettingKey,
                                       InvalidSettingModification,
                                       InvalidSettingValue)
from backend.db import __DATABASE_FILEPATH__, __DATABASE_VERSION__, get_db
from backend.files import folder_path
from backend.logging import log_levels, set_log_level

default_settings = {
	'host': '0.0.0.0',
	'port': 5656,
	'url_base': '',
	'api_key': None,
	'comicvine_api_key': '',
	'auth_password': '',
	'volume_folder_naming': '{series_name}' + path_sep + 'Volume {volume_number} ({year})',
	'file_naming': '{series_name} ({year}) Volume {volume_number} Issue {issue_number}',
	'file_naming_tpb': '{series_name} ({year}) Volume {volume_number} TPB',
	'download_folder': folder_path('temp_downloads'),
	'log_level': 'info',
	'database_version': __DATABASE_VERSION__,
	'unzip': False,
	'volume_padding': 2,
	'issue_padding': 3,
	'rename_downloaded_files': True,
	'file_naming_empty': '{series_name} ({year}) Volume {volume_number} Issue {issue_number}',
	'volume_as_empty': True
}

private_settings = {
	'comicvine_url': 'https://comicvine.gamespot.com',
	'comicvine_api_url': 'https://comicvine.gamespot.com/api',
	'getcomics_url': 'https://getcomics.org',
	'hosting_threads': 10,
	'version': 'v1.0.0-beta-2',
	'python_version': ".".join(str(i) for i in list(version_info))
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

blocklist_reasons = {
	1: 'Link broken',
	2: 'Source not supported',
	3: 'No supported or working links',
	4: 'Added by user'
}

credential_sources = ('mega',)

supported_source_strings = (('mega', 'mega link'),
							('mediafire', 'mediafire link'),
							('getcomics', 'download now','main server','mirror download','link 1','link 2'))

def update_manifest(url_base: str) -> None:
	with open(folder_path('frontend', 'static', 'json', 'manifest.json'), 'r+') as f:
		manifest = loads(f.read())
		manifest['start_url'] = url_base + '/'
		manifest['icons'][0]['src'] = f'{url_base}/static/img/favicon.svg'
		f.seek(0)
		f.write(dumps(manifest, indent=4))
	return

class Settings:
	"""For interacting with the settings
	"""	
	cache = {}
	
	def get_settings(self, use_cache: bool=True) -> dict:
		"""Get all settings and their values

		Args:
			use_cache (bool, optional): Wether or not to use the cache instead of going to the database. Defaults to True.

		Returns:
			dict: All settings and their values
		"""		
		if not use_cache or not self.cache:
			settings = dict(get_db().execute(
				"SELECT key, value FROM config;"
			))
			settings['unzip'] = settings['unzip'] == 1
			settings['rename_downloaded_files'] = settings['rename_downloaded_files'] == 1
			settings['volume_as_empty'] = settings['volume_as_empty'] == 1
			self.cache.update(settings)

		return self.cache

	def set_settings(self, settings: dict) -> dict:
		"""Change the values of settings

		Args:
			settings (dict): The keys and (new) values of settings

		Raises:
			InvalidSettingValue: The value of a setting is not allowed
			InvalidSettingModification: The setting is not allowed to be modified this way
			FolderNotFound: The folder was not found
			InvalidSettingKey: The key isn't recognised

		Returns:
			dict: The settings and their new values. Same format as settings.Settings.get_settings()
		"""		
		from backend.naming import check_format

		logging.debug(f'Setting settings: {settings}')
		cursor = get_db()
		setting_changes = []
		for key, value in settings.items():
			if key == 'port' and not value.isdigit():
				raise InvalidSettingValue(key, value)

			elif key == 'api_key':
				raise InvalidSettingModification(key, 'POST /settings/api_key')

			elif key == 'comicvine_api_key':
				from backend.comicvine import ComicVine
				if not ComicVine(value).test_token():
					raise InvalidSettingValue(key, value)

			elif key == 'download_folder' and not isdir(value):
				raise FolderNotFound

			elif key in ('rename_downloaded_files', 'volumes_as_empty'):
				if not isinstance(value, bool):
					raise InvalidSettingValue(key, value)
				value = int(value)

			elif key in ('volume_folder_naming','file_naming','file_naming_tpb','file_naming_empty'):
				check_format(value, key)

			elif key == 'log_level' and not value in log_levels:
				raise InvalidSettingValue(key, value)

			elif key == 'url_base':
				if value:
					value = ('/' + value.lstrip('/')).rstrip('/')
					settings['url_base'] = value

			elif key in ('issue_padding', 'volume_padding'):
				try:
					if not (1 <= value <= 3):
						raise InvalidSettingValue(key, value)
				except TypeError:
					raise InvalidSettingValue(key, value)

			elif key not in default_settings.keys():
				raise InvalidSettingKey(key)

			setting_changes.append((value, key))

		if setting_changes:
			cursor.executemany(
				"UPDATE config SET value = ? WHERE key = ?;",
				setting_changes
			)

			if 'log_level' in settings:
				set_log_level(settings['log_level'])

			if 'url_base' in settings:
				update_manifest(settings['url_base'])

			result = self.get_settings(use_cache=False)
		else:
			result = self.get_settings()
		logging.info(f'Settings changed: {", ".join(str(s[1]) + "->" + str(s[0]) for s in setting_changes)}')

		return result

	def reset_setting(self, key: str) -> dict:
		"""Reset a setting's value

		Args:
			key (str): The key of the setting of which to reset the value

		Raises:
			InvalidSettingKey: The key isn't recognised

		Returns:
			dict: The settings and their new values. Same format as settings.Settings.get_settings()
		"""		
		logging.debug(f'Setting reset: {key}')
		if not key in default_settings:
			raise InvalidSettingKey(key)
		
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = ?",
			(default_settings[key], key)
		)
		logging.info(f'Setting reset: {key}->{default_settings[key]}')
		return self.get_settings(use_cache=False)
		
	def generate_api_key(self) -> dict:
		"""Generate a new api key

		Returns:
			dict: The settings and their new value. Same format as settings.Settings.get_settings()
		"""		
		logging.debug('Generating new api key')
		api_key = urandom(16).hex()
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = 'api_key';",
			(api_key,)
		)
		logging.info(f'Setting api key regenerated: {api_key}')

		return self.get_settings(use_cache=False)

	def get_service_preference(self) -> List[str]:
		"""Get the preference of each service

		Returns:
			List[str]: The services in order of preference
		"""
		result = [
			s[0] for s in
	   		get_db().execute(
				"SELECT source FROM service_preference ORDER BY pref;"
			)
		]
		return result

	def set_service_preference(self, order: List[str]) -> None:
		"""Update the service preference

		Args:
			order (List[str]): A list with the services, in order of preference
		"""
		logging.info(f'Updating service preference: {order}')
		cursor = get_db()
		cursor.connection.isolation_level = None
		cursor.execute("BEGIN TRANSACTION;")
		cursor.execute("UPDATE service_preference SET pref = NULL;")
		cursor.executemany(
			"UPDATE service_preference SET pref = ? WHERE source = ?;",
			zip(range(1, len(order) + 1), order)
		)
		cursor.execute("COMMIT;")
		cursor.connection.isolation_level = ""

		return
