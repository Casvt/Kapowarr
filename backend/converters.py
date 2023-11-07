#-*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from os.path import splitext

from backend.files import rename_file


class FileConverter(ABC):
	source_format: str
	target_format: str

	@abstractmethod
	def convert(file: str) -> str:
		"""Convert a file from source_format to target_format.

		Args:
			file (str): Filepath to the source file, should be in source_format.

		Returns:
			str: The filepath to the converted file, in target_format.
		"""
		pass

class ZIPtoCBZ(FileConverter):
	source_format = 'zip'
	target_format = 'cbz'

	@staticmethod
	def convert(file: str) -> str:
		target = splitext(file)[0] + '.cbz'
		rename_file(
			file,
			target
		)
		return target
