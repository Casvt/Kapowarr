#-*- coding: utf-8 -*-

import logging


class FolderNotFound(Exception):
	"""Folder not found
	"""
	api_response = {'error': 'FolderNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Folder not found')
		return

class RootFolderNotFound(Exception):
	"""A root folder with the given id doesn't exist
	"""
	api_response = {'error': 'RootFolderNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Rootfolder with given id not found')
		return

class RootFolderInUse(Exception):
	"""A root folder with the given id is requested to be deleted but is used by a volume
	"""
	api_response = {'error': 'RootFolderInUse', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		logging.warning('Rootfolder is still in use')
		return

class VolumeNotFound(Exception):
	"""The volume with the given (comicvine-) key was not found
	"""
	api_response = {'error': 'VolumeNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Volume with given id not found')
		return

class VolumeNotMatched(Exception):
	"""The volume with the given id was found in the database but the comicvine id returned nothing
	"""
	api_response = {'error': 'VolumeNotMatched', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		logging.warning('Volume not matched with comicvine database')
		return

class CVRateLimitReached(Exception):
	"""The rate limit of the ComicVine API is reached
	"""	
	api_response = {'error': 'CVRateLimitReached', 'result': {}, 'code': 509}
	
	def __init__(self) -> None:
		logging.warning('Comic Vine API rate limit reached')
		return

class VolumeAlreadyAdded(Exception):
	"""The volume that is desired to be added is already added
	"""
	api_response = {'error': 'VolumeAlreadyAdded', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		logging.warning('Volume is already added')
		return
	
class VolumeDownloadedFor(Exception):
	"""The volume is desired to be deleted but there is a download for it going
	"""	
	def __init__(self, volume_id: int):
		self.volume_id = volume_id
		super().__init__(self.volume_id)
		logging.warning(f'Deleting volume failed because there is a download for the volume: {self.volume_id}')
		return
		
	@property
	def api_response(self):
		return {'error': 'VoolumeDownloadedFor', 'result': {'volume_id': self.volume_id}, 'code': 400}

class IssueNotFound(Exception):
	"""The issue with the given id was not found
	"""
	api_response = {'error': 'IssueNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Issue with given id not found')
		return

class TaskNotFound(Exception):
	"""The task with the given id was not found
	"""
	api_response = {'error': 'TaskNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Task with given id not found')
		return

class TaskNotDeletable(Exception):
	"""The task could not be deleted because it's the first in the queue
	"""
	api_response = {'error': 'TaskNotDeletable', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		logging.warning('Task with given id is not deletable')
		return

class DownloadNotFound(Exception):
	"""The download requested to be deleted was not found
	"""
	api_response = {'error': 'DownloadNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Download with given id not found')
		return

class BlocklistEntryNotFound(Exception):
	"""The blocklist entry with the given id was not found
	"""
	api_response = {'error': 'BlocklistEntryNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Blocklist entry with given id not found')
		return

class InvalidComicVineApiKey(Exception):
	"""No Comic Vine API key is set or it's invalid
	"""
	api_response = {'error': 'InvalidComicVineApiKey', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		logging.warning('The ComicVine API key is not set or is invalid')
		return

class LinkBroken(Exception):
	"""The download link doesn't work
	"""
	def __init__(self, reason_id: int, reason_text: str):
		self.reason_id = reason_id
		self.reason_text = reason_text
		super().__init__(self.reason_id)
		return
	
	@property
	def api_response(self):
		return {'error': 'LinkBroken', 'result': {'reason_text': self.reason_text, 'reason_id': self.reason_id}, 'code': 400}

class InvalidSettingKey(Exception):
	"""The setting key is unknown
	"""
	def __init__(self, key: str=''):
		self.key = key
		super().__init__(self.key)
		logging.warning(f'No setting matched the given key: {key}')
		return

	@property
	def api_response(self):
		return {'error': 'InvalidSettingKey', 'result': {'key': self.key}, 'code': 400}

class InvalidSettingValue(Exception):
	"""The setting value is invalid
	"""
	def __init__(self, key: str='', value: str=''):
		self.key = key
		self.value = value
		super().__init__(self.key)
		logging.warning(f'The value for this setting is invalid: {key}: {value}')
		return
		
	@property
	def api_response(self):
		return {'error': 'InvalidSettingValue', 'result': {'key': self.key, 'value': self.value}, 'code': 400}

class InvalidSettingModification(Exception):
	"""The setting is not allowed to be changed this way
	"""
	def __init__(self, key: str='', instead: str=''):
		self.key = key
		self.instead = instead
		super().__init__(key)
		logging.warning(f'This setting is not allowed to be changed this way: {key}. Instead: {instead}')
		return

	@property
	def api_response(self):
		return {'error': 'InvalidSettingModification', 'result': {'key': self.key, 'instead': self.instead}, 'code': 400}

class KeyNotFound(Exception):
	"""A key that is required to be given in the api request was not found
	"""
	def __init__(self, key: str=''):
		self.key = key
		super().__init__(self.key)
		if key != 'password':
			logging.warning(f'This key was not found in the API request, eventhough it\'s required: {key}')
		return

	@property
	def api_response(self):
		return {'error': 'KeyNotFound', 'result': {'key': self.key}, 'code': 400}

class InvalidKeyValue(Exception):
	"""A key given in the api request has an invalid value
	"""
	def __init__(self, key: str='', value: str=''):
		self.key = key
		self.value = value
		super().__init__(self.key)
		if value not in ('undefined', 'null'):
			logging.warning(f'This key in the API request has an invalid value: {key} = {value}')
		return

	@property
	def api_response(self):
		return {'error': 'InvalidKeyValue', 'result': {'key': self.key, 'value': self.value}, 'code': 400}

class CredentialNotFound(Exception):
	"""The credential with the given id was not found
	"""	
	api_response = {'error': 'CredentialNotFound', 'result': {}, 'code': 404}
	
	def __init__(self) -> None:
		logging.warning('Credential with given id not found')
		return

class CredentialSourceNotFound(Exception):
	"""The credential source with the given string was not found
	"""	
	def __init__(self, string: str) -> None:
		self.string = string
		logging.warning(f'Credential source with given string not found: {string}')
		return

	@property
	def api_response(self):
		return {'error': 'CredentialSourceNotFound', 'result': {'string': self.string}, 'code': 404}

class CredentialAlreadyAdded(Exception):
	"""A credential for the given source is already added
	"""	
	api_response = {'error': 'CredentialAlreadyAdded', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		logging.warning('A credential for the given source is already added')
		return

class CredentialInvalid(Exception):
	"""A credential is incorrect (can't login with it)
	"""
	api_response = {'error': 'CredentialInvalid', 'result': {}, 'code': 400}
	
	def __init__(self) -> None:
		return

class DownloadLimitReached(Exception):
	"""The download limit (download quota) for the service is reached
	"""
	def __init__(self, string: str) -> None:
		self.string = string
		logging.warning(f'Credential source {string} has reached it\'s download limit')
		return
	
	@property
	def api_response(self):
		return {'error': 'DownloadLimitReached', 'result': {'string': self.string}, 'code': 509}
	