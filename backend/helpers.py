#-*- coding: utf-8 -*-

"""General "helper" functions
"""

import logging
from os import remove
from os.path import isdir, isfile
from shutil import rmtree
from sys import version_info


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

class SeedingHandling:
	"Enum-like class for the seeding_handling setting"

	COMPLETE = 'complete'
	"Let torrent complete (finish seeding) and then move all files"

	COPY = 'copy'
	"Copy the files while the torrent is seeding, then delete original files"

	def __contains__(self, value) -> bool:
		return value in (self.COMPLETE, self.COPY)
