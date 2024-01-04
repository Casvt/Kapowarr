#-*- coding: utf-8 -*-

"""
General "helper" functions
"""

import logging
from os import remove
from os.path import isdir, isfile
from shutil import rmtree
from sys import version_info
from threading import current_thread
from typing import Iterable, Union


def get_python_version() -> str:
	"""Get python version as string

	Returns:
		str: The python version
	"""
	return ".".join(
		str(i) for i in list(version_info)
	)

def check_python_version() -> bool:
	"""Check if the python version that is used is a minimum version.

	Returns:
		bool: Whether or not the python version is version 3.8 or above or not.
	"""
	if not (version_info.major == 3 and version_info.minor >= 8):
		logging.critical(
			'The minimum python version required is python3.8 ' + 
			'(currently ' + version_info.major + '.' + version_info.minor + '.' + version_info.micro + ').'
		)
		return False
	return True

def batched(l: list, n: int):
	"""Iterate over list (or tuple, set, etc.) in batches

	Args:
		l (list): The list to iterate over
		n (int): The batch size

	Yields:
		A batch of size n from l
	"""
	for ndx in range(0, len(l), n):
		yield l[ndx : ndx+n]

def delete_file_folder(path: str) -> None:
	"""Delete a file or folder. In the case of a folder, it is deleted recursively.

	Args:
		path (str): The path to the file or folder.
	"""
	if isfile(path):
		remove(path)
	elif isdir(path):
		rmtree(path, ignore_errors=True)
	return

class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		c = str(cls)
		if c not in cls._instances:
			cls._instances[c] = super().__call__(*args, **kwargs)

		return cls._instances[c]

class DB_ThreadSafeSingleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		i = f'{cls}{current_thread()}'
		if (i not in cls._instances
		or cls._instances[i].closed):
			cls._instances[i] = super().__call__(*args, **kwargs)

		return cls._instances[i]

class CommaList(list):
	"""
	Normal list but init can also take a string with comma seperated values:
		`'blue,green,red'` -> `['blue', 'green', 'red']`.
	Using str() will convert it back to a string with comma seperated values.
	"""
	
	def __init__(self, value: Union[str, Iterable]):
		if not isinstance(value, str):
			super().__init__(value)
			return

		if not value:
			super().__init__([])
		else:
			super().__init__(value.split(','))
		return

	def __str__(self) -> str:
		return ','.join(self)

class SeedingHandling:
	"Enum-like class for the seeding_handling setting"

	COMPLETE = 'complete'
	"Let torrent complete (finish seeding) and then move all files"

	COPY = 'copy'
	"Copy the files while the torrent is seeding, then delete original files"

	def __contains__(self, value) -> bool:
		return value in (self.COMPLETE, self.COPY)
