#-*- coding: utf-8 -*-

import logging
from abc import ABC, abstractmethod
from os import mkdir, remove, utime
from os.path import basename, dirname, join, splitext, getmtime
from shutil import make_archive, rmtree
from subprocess import call as spc
from sys import platform
from typing import List
from zipfile import ZipFile

from backend.db import get_db
from backend.enums import SpecialVersion
from backend.files import (_list_files, extract_filename_data, folder_path,
                           image_extensions, rename_file, scan_files,
                           supported_extensions)
from backend.naming import mass_rename
from backend.search import _check_matching_titles
from backend.volumes import Volume

archive_extract_folder = '.archive_extract'
rar_executables = {
	'linux': folder_path('backend', 'lib', 'rar_linux_64'),
	'darwin': folder_path('backend', 'lib', 'rar_bsd_64'),
	'win32': folder_path('backend', 'lib', 'rar_windows_64.exe')
}

def __get_volume_data(volume_id: int) -> dict:
	"""Get info about the volume based on ID

	Args:
		volume_id (int): The ID of the volume.

	Returns:
		dict: The data
	"""
	volume_data = dict(get_db(dict).execute("""
		SELECT
			v.id,
			v.title, year,
			volume_number,
			folder,
			special_version,
			MAX(i.date) AS last_issue_date
		FROM volumes v
		INNER JOIN issues i
		ON v.id = i.volume_id
		WHERE v.id = ?
		LIMIT 1;
		""",
		(volume_id,)
	).fetchone())

	volume_data['special_version'] = SpecialVersion(volume_data['special_version'])
	volume_data['annual'] = 'annual' in volume_data['title'].lower()
	if volume_data['last_issue_date']:
		volume_data['end_year'] = int(volume_data['last_issue_date'].split('-')[0])
	else:
		volume_data['end_year'] = volume_data['year']

	return volume_data

def extract_files_from_folder(
	source_folder: str,
	volume_id: int
) -> List[str]:
	volume_data = __get_volume_data(volume_id)
	folder_contents = _list_files(source_folder, supported_extensions)

	cursor = get_db()

	# Filter non-relevant files
	rel_files: List[str] = []
	rel_files_append = rel_files.append
	for c in folder_contents:
		if 'variant cover' in c.lower():
			continue

		result = extract_filename_data(c, False)
		if (_check_matching_titles(result['series'], volume_data['title'])
		and (
			# Year has to match
			(result['year'] is not None
				and volume_data['year'] - 1 <= result['year'] <= volume_data['end_year'] + 1)
			# Or volume number
			or (result['volume_number'] is not None
				and ((
						isinstance(result['volume_number'], int)
						and result['volume_number'] == volume_data['volume_number']
					)
					or (
						volume_data['special_version'] == SpecialVersion.VOLUME_AS_ISSUE
						and cursor.execute("""
							SELECT 1
							FROM issues
							WHERE volume_id = ?
								AND calculated_issue_number = ?
							LIMIT 1;
							""", (
								volume_data['id'],
								result['volume_number']
								if isinstance(result['volume_number'], int) else
								result['volume_number'][0]
							)
						).fetchone()
					)
			))
			# Or neither should be found (we play it safe so we keep those)
			or (result['year'] is None and result['volume_number'] is None)
		)
		and result['annual'] == volume_data['annual']):
			rel_files_append(c)
	logging.debug(f'Relevant files: {rel_files}')

	# Move remaining files to main folder and delete source folder
	result = []
	result_append = result.append
	for c in rel_files:
		if c.endswith(image_extensions):
			dest = join(volume_data["folder"], basename(dirname(c)), basename(c))

		else:
			dest = join(volume_data["folder"], basename(c))
		
		rename_file(c, dest)
		result_append(dest)

	rmtree(source_folder, ignore_errors=True)
	return result

def _run_rar(args: List[str]) -> int:
	"""Run (un)rar executable. This function takes care of the platform.
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

	@abstractmethod
	def convert(file: str) -> str:
		"""Convert a file from source_format to target_format.

		Args:
			file (str): Filepath to the source file, should be in source_format.

		Returns:
			str: The filepath to the converted file, in target_format.
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
		cursor = get_db(dict)

		volume_id: int = cursor.execute("""
			SELECT i.volume_id
			FROM
				files f
				INNER JOIN issues_files if
				INNER JOIN issues i
			ON
				f.id = if.file_id
				AND if.issue_id = i.id
			WHERE f.filepath = ?
			LIMIT 1;
			""",
			(file,)
		).fetchone()[0]

		volume_folder = cursor.execute(
			"SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
			(volume_id,)
		).fetchone()['folder']

		archive_folder = join(volume_folder, archive_extract_folder)

		with ZipFile(file, 'r') as zip:
			zip.extractall(archive_folder)

		_run_rar([
			'a',
			'-ep', '-inul',
			splitext(file)[0],
			archive_folder
		])

		rmtree(archive_folder, ignore_errors=True)

		remove(file)

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
	def convert(file: str) -> str:
		cursor = get_db(dict)

		volume_id: int = cursor.execute("""
			SELECT i.volume_id
			FROM
				files f
				INNER JOIN issues_files if
				INNER JOIN issues i
			ON
				f.id = if.file_id
				AND if.issue_id = i.id
			WHERE f.filepath = ?
			LIMIT 1;
			""",
			(file,)
		).fetchone()[0]

		volume_folder = cursor.execute(
			"SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
			(volume_id,)
		).fetchone()['folder']

		zip_folder = join(
			volume_folder,
			archive_extract_folder,
			splitext(basename(file))[0]
		)

		with ZipFile(file, 'r') as zip:
			zip.extractall(zip_folder)

		resulting_files = extract_files_from_folder(
			dirname(zip_folder),
			volume_id
		)

		scan_files(Volume(volume_id).get_info())
		if resulting_files:
			mass_rename(volume_id, filepath_filter=resulting_files)

		remove(file)

		return volume_folder

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
	def convert(file: str) -> str:
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
		cursor = get_db(dict)

		volume_id: int = cursor.execute("""
			SELECT i.volume_id
			FROM
				files f
				INNER JOIN issues_files if
				INNER JOIN issues i
			ON
				f.id = if.file_id
				AND if.issue_id = i.id
			WHERE f.filepath = ?
			LIMIT 1;
			""",
			(file,)
		).fetchone()[0]

		volume_folder = cursor.execute(
			"SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
			(volume_id,)
		).fetchone()['folder']
		
		rar_folder = join(volume_folder, archive_extract_folder)
		mkdir(rar_folder)

		_run_rar([
			'x',
			'-inul',
			file,
			rar_folder
		])

		for f in _list_files(rar_folder):
			if getmtime(f) <= 315619200:
				utime(f, (315619200, 315619200))

		target_file = splitext(file)[0]
		target_archive = make_archive(target_file, 'zip', rar_folder)

		rmtree(rar_folder, ignore_errors=True)

		remove(file)

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
	def convert(file: str) -> str:
		cursor = get_db(dict)

		volume_id: int = cursor.execute("""
			SELECT i.volume_id
			FROM
				files f
				INNER JOIN issues_files if
				INNER JOIN issues i
			ON
				f.id = if.file_id
				AND if.issue_id = i.id
			WHERE f.filepath = ?
			LIMIT 1;
			""",
			(file,)
		).fetchone()[0]

		volume_folder = cursor.execute(
			"SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
			(volume_id,)
		).fetchone()['folder']
		
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
			dirname(rar_folder),
			volume_id
		)

		scan_files(Volume(volume_id).get_info())
		if resulting_files:
			mass_rename(volume_id, filepath_filter=resulting_files)

		remove(file)

		return volume_folder

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
	def convert(file: str) -> str:
		return RARtoFOLDER.convert(file)

#=====================
# FOLDER
#=====================
# FOLDER to ZIP

# FOLDER to CBZ

# FOLDER to RAR

# FOLDER TO CBR
