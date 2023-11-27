#-*- coding: utf-8 -*-

import logging
from abc import ABC, abstractmethod
from os import remove
from os.path import basename, join, splitext
from shutil import rmtree
from typing import List, Tuple
from zipfile import ZipFile

from backend.db import get_db
from backend.files import (_list_files, extract_filename_data,
                           image_extensions, rename_file, scan_files,
                           supported_extensions)
from backend.naming import mass_rename
from backend.search import _check_matching_titles
from backend.volumes import Volume

zip_extract_folder = '.zip_extract'


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

class ZIPtoFOLDER(FileConverter):
	source_format = 'zip'
	target_format = 'folder'
	
	@staticmethod
	def convert(file: str) -> str:
		cursor = get_db('dict')

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
		
		zip_folder = join(volume_folder, zip_extract_folder)

		with ZipFile(file, 'r') as zip:
			zip.extractall(zip_folder)

		remove(file)

		resulting_files = extract_files_from_folder(
			zip_folder,
			volume_id
		)

		scan_files(Volume(volume_id).get_info())
		if resulting_files:
			mass_rename(volume_id, filepath_filter=resulting_files)

		return volume_folder

def __get_volume_data(volume_id: int) -> dict:
	"""Get info about the volume based on ID

	Args:
		volume_id (int): The ID of the volume.

	Returns:
		dict: The data
	"""
	volume_data = dict(get_db('dict').execute("""
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
	rel_files: List[Tuple[str, dict]] = []
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
						volume_data[4] == 'volume-as-issue'
						and cursor.execute(
							"SELECT 1 FROM issues WHERE volume_id = ? AND calculated_issue_number = ? LIMIT 1;",
							(
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
			rel_files_append((c, result))
	logging.debug(f'Relevant files: {rel_files}')

	# Delete non-relevant files
	for c in folder_contents:
		if not any(r for r in rel_files if r[0] == c):
			remove(c)

	# Move remaining files to main folder and delete source folder
	result = []
	result_append = result.append
	for c, c_info in rel_files:
		if c.endswith(image_extensions):
			intermediate_folder = (f'{volume_data["title"]} ({volume_data["year"]})'
				+ f'Volume {c_info["volume_number"] if isinstance(c_info["volume_number"], int) else "-".join(map(str, c_info))}')

			if volume_data['special_version'] and volume_data['special_version'] != 'volume-as-issue':
				intermediate_folder += f' {volume_data["special_version"]}'
			elif not (volume_data["special_version"] == 'volume-as-issue'):
				intermediate_folder += f' {c_info["issue_number"]}'

			dest = join(volume_data["folder"], intermediate_folder, basename(c))

		else:
			dest = join(volume_data["folder"], basename(c))
		
		rename_file(c, dest)
		result_append(dest)

	rmtree(source_folder, ignore_errors=True)
	return result
