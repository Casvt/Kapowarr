#-*- coding: utf-8 -*-

"""This file contains custom exceptions
"""

class FolderNotFound(Exception):
	"""Folder not found
	"""
	api_response = {'error': 'FolderNotFound', 'result': {}}, 404

class RootFolderNotFound(Exception):
	"""A root folder with the given id doesn't exist
	"""
	api_response = {'error': 'RootFolderNotFound', 'result': {}}, 404

class RootFolderInUse(Exception):
	"""A root folder with the given id is used by a volume but is requested to be deleted
	"""
	api_response = {'error': 'RootFolderInUse', 'result': {}}, 400

class VolumeNotFound(Exception):
	"""The volume with the given (comicvine-) key was not found
	"""
	api_response = {'error': 'VolumeNotFound', 'result': {}}, 404

class VolumeNotMatched(Exception):
	"""The volume with the given id was found in the database but the comicvine id returned nothing
	"""
	api_response = {'error': 'VolumeNotMatched', 'result': {}}, 400

class VolumeAlreadyAdded(Exception):
	"""The volume that is desired to be added is already added
	"""
	api_response = {'error': 'VolumeAlreadyAdded', 'result': {}}, 400

class IssueNotFound(Exception):
	"""The issue with the given id was not found
	"""
	api_response = {'error': 'IssueNotFound', 'result': {}}, 404

class TaskNotFound(Exception):
	"""The task with the given id was not found
	"""
	api_response = {'error': 'TaskNotFound', 'result': {}}, 404

class TaskNotDeletable(Exception):
	"""The task could not be deleted because it's the first in the queue
	"""
	api_response = {'error': 'TaskNotDeletable', 'result': {}}, 400

class DownloadNotFound(Exception):
	"""The download requested to be deleted was not found
	"""
	api_response = {'error': 'DownloadNotFound', 'result': {}}, 404

class BlocklistEntryNotFound(Exception):
	"""The blocklist entry with the given id was not found
	"""
	api_response = {'error': 'BlocklistEntryNotFound', 'result': {}}, 404

class InvalidComicVineApiKey(Exception):
	"""No Comic Vine api key is set or it's invalid
	"""
	api_response = {'error': 'InvalidComicVineApiKey', 'result': {}}, 400

class LinkBroken(Exception):
	"""The download link doesn't work
	"""
	def __init__(self, reason_id: int, reason_text: str):
		self.reason_id = reason_id
		self.reason_text = reason_text
		super().__init__(self.reason_id)
	
	@property
	def api_response(self):
		return {'error': 'LinkBroken', 'result': {'reason_text': self.reason_text, 'reason_id': self.reason_id}}, 400

class InvalidSettingKey(Exception):
	"""The setting key is unknown
	"""
	def __init__(self, key: str=''):
		self.key = key
		super().__init__(self.key)

	@property
	def api_response(self):
		return {'error': 'InvalidSettingKey', 'result': {'key': self.key}}, 400

class InvalidSettingValue(Exception):
	"""The setting value is invalid
	"""
	def __init__(self, key: str=''):
		self.key = key
		super().__init__(self.key)
		
	@property
	def api_response(self):
		return {'error': 'InvalidSettingValue', 'result': {'key': self.key}}, 400

class InvalidSettingModification(Exception):
	"""The setting is not allowed to be changed this way
	"""
	def __init__(self, key: str='', instead: str=''):
		self.key = key
		self.instead = instead
		super().__init__(key)
		
	@property
	def api_response(self):
		return {'error': 'InvalidSettingModification', 'result': {'key': self.key, 'instead': self.instead}}, 400

class KeyNotFound(Exception):
	"""A key that is required to be given in the api request was not found
	"""
	def __init__(self, key: str=''):
		self.key = key
		super().__init__(self.key)
	
	@property
	def api_response(self):
		return {'error': 'KeyNotFound', 'result': {'key': self.key}}, 400

class InvalidKeyValue(Exception):
	"""A key given in the api request has an invalid value
	"""
	def __init__(self, key: str='', value: str=''):
		self.key = key
		self.value = value
		super().__init__(self.key)
	
	@property
	def api_response(self):
		return {'error': 'InvalidKeyValue', 'result': {'key': self.key, 'value': self.value}}, 400
