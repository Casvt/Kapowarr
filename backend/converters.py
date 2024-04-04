#-*- coding: utf-8 -*-

"""
Contains all the converters for converting from one format to another
"""

import logging
from abc import ABC, abstractmethod
from os import mkdir, utime
from os.path import basename, dirname, getmtime, join, sep, splitext
from shutil import make_archive
from subprocess import call as spc
from sys import platform
from typing import List, Union
from zipfile import ZipFile

from backend.file_extraction import (extract_filename_data, image_extensions,
                                     md_extensions, md_files,
                                     supported_extensions)
from backend.files import (create_folder, delete_empty_folders,
                           delete_file_folder, filepath_to_volume_id,
                           folder_path, list_files, rename_file)
from backend.helpers import extract_year_from_date
from backend.matching import folder_extraction_filter
from backend.naming import mass_rename
from backend.volumes import Volume, scan_files

archive_extract_folder = '.archive_extract'
rar_executables = {
	'linux': folder_path('backend', 'lib', 'rar_linux_64'),
	'darwin': folder_path('backend', 'lib', 'rar_bsd_64'),
	'win32': folder_path('backend', 'lib', 'rar_windows_64.exe')
}
"Maps a platform name to it's rar executable"

def extract_files_from_folder(
	source_folder: str,
	volume_id: int
) -> List[str]:
	"""Move files out of folder in to volume folder,
	but only if they match to the volume. Otherwise they are deleted,
	together with the original folder.

	Args:
		source_folder (str): The folder to extract files out of.
		volume_id (int): The ID for which the files should be.

	Returns:
		List[str]: The filepaths of the files that were extracted.
	"""
	folder_contents = list_files(
		source_folder,
		(*supported_extensions, *md_extensions)
	)

	volume = Volume(volume_id)
	volume_data = volume.get_keys(
		('id', 'title', 'year', 'folder')
	)
	end_year = extract_year_from_date(
		volume['last_issue_date'],
		volume_data.year
	)

	# Filter non-relevant files
	rel_files = [
		c
		for c in folder_contents
		if (
			not 'variant cover' in c.lower()
			and (
				basename(c).lower() in md_files
				or
				folder_extraction_filter(
					extract_filename_data(c, False),
					volume_data,
					end_year
				)
			)
		)
	]
	logging.debug(f'Relevant files: {rel_files}')

	# Move remaining files to main folder and delete source folder
	result = []
	result_append = result.append
	for c in rel_files:
		if c.endswith(image_extensions):
			dest = join(volume_data.folder, basename(dirname(c)), basename(c))

		else:
			dest = join(volume_data.folder, basename(c))

		rename_file(c, dest, True)
		result_append(dest)

	delete_file_folder(source_folder)
	return result

def _run_rar(args: List[str]) -> int:
	"""Run rar executable. This function takes care of the platform.
		Note: It is already expected when this function is called
		that the platform is supported. The check should be done outside.

	Args:
		args (List[str]): The arguments to give to the executable.

	Returns:
		int: The exit code of the executable.
	"""
	exe = rar_executables[platform]

	return spc([exe, *args])

class FileConverter(ABC):
	source_format: str
	target_format: str

	@staticmethod
	@abstractmethod
	def convert(file: str) -> Union[str, List[str]]:
		"""Convert a file from source_format to target_format.

		Args:
			file (str): Filepath to the source file, should be in source_format.

		Returns:
			Union[str, List[str]]: The resulting files or directories, in target_format.
		"""
		pass

#=====================
# ZIP
#=====================
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

class ZIPtoRAR(FileConverter):
	source_format = 'zip'
	target_format = 'rar'

	@staticmethod
	def convert(file: str) -> str:
		volume_id = filepath_to_volume_id(file)
		volume_folder = Volume(volume_id)['folder']
		archive_folder = join(
			volume_folder,
			archive_extract_folder,
			splitext(basename(file))[0]
		)

		with ZipFile(file, 'r') as zip:
			zip.extractall(archive_folder)

		_run_rar([
			'a',
			'-ep', '-inul',
			splitext(file)[0],
			archive_folder
		])

		delete_file_folder(archive_folder)
		delete_file_folder(file)
		delete_empty_folders(dirname(file), volume_folder)
		delete_empty_folders(dirname(archive_folder), volume_folder)

		return splitext(file)[0] + '.rar'

class ZIPtoCBR(FileConverter):
	source_format = 'zip'
	target_format = 'cbr'

	@staticmethod
	def convert(file: str) -> str:
		rar_file = ZIPtoRAR.convert(file)
		cbr_file = RARtoCBR.convert(rar_file)
		return cbr_file

class ZIPtoFOLDER(FileConverter):
	source_format = 'zip'
	target_format = 'folder'

	@staticmethod
	def convert(file: str) -> List[str]:
		volume_id = filepath_to_volume_id(file)
		volume_folder = Volume(volume_id)['folder']
		zip_folder = join(
			volume_folder,
			archive_extract_folder,
			splitext('_'.join(file.split(sep)))[0]
		)

		with ZipFile(file, 'r') as zip:
			zip.extractall(zip_folder)

		resulting_files = extract_files_from_folder(
			zip_folder,
			volume_id
		)

		if resulting_files:
			scan_files(volume_id)
			resulting_files = mass_rename(
				volume_id,
				filepath_filter=resulting_files
			)

		delete_file_folder(zip_folder)
		delete_file_folder(file)
		delete_empty_folders(dirname(file), volume_folder)
		delete_empty_folders(dirname(zip_folder), volume_folder)

		return resulting_files

#=====================
# CBZ
#=====================
class CBZtoZIP(FileConverter):
	source_format = 'cbz'
	target_format = 'zip'

	@staticmethod
	def convert(file: str) -> str:
		target = splitext(file)[0] + '.zip'
		rename_file(
			file,
			target
		)
		return target

class CBZtoRAR(FileConverter):
	source_format = 'cbz'
	target_format = 'rar'

	@staticmethod
	def convert(file: str) -> str:
		return ZIPtoRAR.convert(file)

class CBZtoCBR(FileConverter):
	source_format = 'cbz'
	target_format = 'cbr'

	@staticmethod
	def convert(file: str) -> str:
		rar_file = ZIPtoRAR.convert(file)
		cbr_file = RARtoCBR.convert(rar_file)
		return cbr_file

class CBZtoFOLDER(FileConverter):
	source_format = 'cbz'
	target_format = 'folder'

	@staticmethod
	def convert(file: str) -> List[str]:
		return ZIPtoFOLDER.convert(file)

#=====================
# RAR
#=====================
class RARtoCBR(FileConverter):
	source_format = 'rar'
	target_format = 'cbr'

	@staticmethod
	def convert(file: str) -> str:
		target = splitext(file)[0] + '.cbr'
		rename_file(
			file,
			target
		)
		return target

class RARtoZIP(FileConverter):
	source_format = 'rar'
	target_format = 'zip'

	@staticmethod
	def convert(file: str) -> str:
		volume_id = filepath_to_volume_id(file)
		volume_folder = Volume(volume_id)['folder']
		rar_folder = join(
			volume_folder,
			archive_extract_folder,
			splitext(basename(file))[0]
		)

		create_folder(rar_folder)

		_run_rar([
			'x',
			'-inul',
			file,
			rar_folder
		])

		for f in list_files(rar_folder):
			if getmtime(f) <= 315619200:
				utime(f, (315619200, 315619200))

		target_file = splitext(file)[0]
		target_archive = make_archive(target_file, 'zip', rar_folder)

		delete_file_folder(rar_folder)
		delete_file_folder(file)
		delete_empty_folders(dirname(file), volume_folder)
		delete_empty_folders(dirname(rar_folder), volume_folder)

		return target_archive

class RARtoCBZ(FileConverter):
	source_format = 'rar'
	target_format = 'cbz'

	@staticmethod
	def convert(file: str) -> str:
		zip_file = RARtoZIP.convert(file)
		cbz_file = ZIPtoCBZ.convert(zip_file)
		return cbz_file

class RARtoFOLDER(FileConverter):
	source_format = 'rar'
	target_format = 'folder'

	@staticmethod
	def convert(file: str) -> List[str]:
		volume_id = filepath_to_volume_id(file)
		volume_folder = Volume(volume_id)['folder']
		rar_folder = join(
			volume_folder,
			archive_extract_folder,
			splitext(basename(file))[0]
		)

		mkdir(rar_folder)

		_run_rar([
			'x',
			'-inul',
			file,
			rar_folder
		])

		resulting_files = extract_files_from_folder(
			rar_folder,
			volume_id
		)

		if resulting_files:
			scan_files(volume_id)
			resulting_files = mass_rename(
				volume_id,
				filepath_filter=resulting_files
			)

		delete_file_folder(rar_folder)
		delete_file_folder(file)
		delete_empty_folders(dirname(file), volume_folder)
		delete_empty_folders(dirname(rar_folder), volume_folder)

		return resulting_files

#=====================
# CBR
#=====================
class CBRtoRAR(FileConverter):
	source_format = 'cbr'
	target_format = 'rar'

	@staticmethod
	def convert(file: str) -> str:
		target = splitext(file)[0] + '.rar'
		rename_file(
			file,
			target
		)
		return target

class CBRtoZIP(FileConverter):
	source_format = 'cbr'
	target_format = 'zip'

	@staticmethod
	def convert(file: str) -> str:
		return RARtoZIP.convert(file)

class CBRtoCBZ(FileConverter):
	source_format = 'cbr'
	target_format = 'cbz'

	@staticmethod
	def convert(file: str) -> str:
		zip_file = RARtoZIP.convert(file)
		cbz_file = ZIPtoCBZ.convert(zip_file)
		return cbz_file

class CBRtoFOLDER(FileConverter):
	source_format = 'cbr'
	target_format = 'folder'

	@staticmethod
	def convert(file: str) -> List[str]:
		return RARtoFOLDER.convert(file)

#=====================
# FOLDER
#=====================
# FOLDER to ZIP

# FOLDER to CBZ

# FOLDER to RAR

# FOLDER TO CBR
