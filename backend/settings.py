#-*- coding: utf-8 -*-

"""This file contains functions regarding the settings
"""

import logging
from os import urandom
from os.path import isdir, isfile
from os.path import sep as path_sep
from sys import version_info

from backend.custom_exceptions import (FolderNotFound, InvalidSettingKey,
                                       InvalidSettingModification,
                                       InvalidSettingValue)
from backend.db import __DATABASE_VERSION__, get_db
from backend.files import folder_path
from backend.helpers import set_log_level

default_settings = {
	'host': '0.0.0.0',
	'port': 5656,
	'comicvine_api_key': '',
	'auth_password': '',
	'volume_folder_naming': '{series_name}' + path_sep + 'Volume {volume_number} ({year})',
	'file_naming': '{series_name} ({year}) Volume {volume_number} Issue {issue_number}',
	'file_naming_tpb': '{series_name} ({year}) Volume {volume_number} TPB',
	'download_folder': folder_path('temp_downloads'),
	'log_level': 'info',
	'database_version': __DATABASE_VERSION__
}

private_settings = {
	'comicvine_api_url': 'https://comicvine.gamespot.com/api',
	'getcomics_url': 'https://getcomics.info',
	'hosting_threads': 10,
	'version': '1.0.0-beta',
	'python_version': ".".join(str(i) for i in list(version_info))
}

task_intervals = {
	# Tasks at the same interval, but that should be
	# run after each other should be put in that order in this dict
	'update_all': 86400, # 1 day
	'search_all': 86400 # 1 day
}

blocklist_reasons = {
	1: 'Link broken',
	2: 'Source not supported',
	3: 'No supported or working links',
	4: 'Added by user'
}

class Settings:
	cache = {}
	
	def get_settings(self, use_cache: bool=True) -> dict:
		if not self.cache or use_cache == False:
			settings = dict(get_db().execute(
				"SELECT key, value FROM config;"
			).fetchall())
			self.cache.update(settings)

		return self.cache

	def set_settings(self, settings: dict) -> dict:
		from backend.naming import check_format

		cursor = get_db()
		setting_changes = []
		for key, value in settings.items():
			if key == 'port' and not value.isdigit():
				raise InvalidSettingValue(key)

			elif key == 'api_key':
				raise InvalidSettingModification(key, 'POST /settings/api_key')

			elif key == 'download_folder' and not isdir(value):
				raise FolderNotFound

			elif key in ('volume_folder_naming','file_naming','file_naming_tpb'):
				check_format(value, key)

			elif key == 'log_level' and not value in ('info', 'debug'):
				raise InvalidSettingValue(key)
				
			elif key == 'log_file' and not isfile(value):
				raise InvalidSettingValue(key)

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

			result = self.get_settings(use_cache=False)
		else:
			result = self.get_settings()
		logging.info(f'Settings changed: {", ".join(s[1] + "->" + s[0] for s in setting_changes)}')

		return result

	def reset_setting(self, key: str) -> dict:
		if not key in default_settings:
			raise InvalidSettingKey(key)
		
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = ?",
			(default_settings[key], key)
		)
		logging.info(f'Setting reset: {key}->{default_settings[key]}')
		return self.get_settings(use_cache=False)
		
	def generate_api_key(self) -> dict:
		api_key = urandom(16).hex()
		get_db().execute(
			"UPDATE config SET value = ? WHERE key = 'api_key';",
			(api_key,)
		)
		logging.info(f'Setting api key regenerated: {api_key}')

		return self.get_settings(use_cache=False)
