#-*- coding: utf-8 -*-

"""This file contains functions regarding the post processing of downloads
"""

import logging
from os import remove
from os.path import basename, exists, join
from shutil import move, rmtree
from time import time
from typing import List, Tuple
from zipfile import ZipFile
from backend.conversion import find_target_format_file

from backend.db import get_db
from backend.files import (_list_files, extract_filename_data,
                           image_extensions, rename_file, supported_extensions)
from backend.naming import mass_rename
from backend.search import _check_matching_titles
from backend.volumes import Volume, scan_files

zip_extract_folder = '.zip_extract'

class PostProcessingActions:
	@staticmethod
	def remove_from_queue(download) -> None:
		"Delete the download from the queue in the database"
		get_db().execute(
			"DELETE FROM download_queue WHERE id = ?",
			(download.id,)
		)
		return

	@staticmethod
	def add_to_history(download) -> None:
		"Add the download to history in the database"
		get_db().execute(
			"""
			INSERT INTO download_history(original_link, title, downloaded_at)
			VALUES (?,?,?);
			""",
			(download.page_link, download.title, round(time()))
		)
		return

	@staticmethod
	def move_file(download) -> None:
		"Move file from download folder to final destination"
		if exists(download.file):
			folder = get_db().execute(
				"SELECT folder FROM volumes WHERE id = ? LIMIT 1",
				(download.volume_id,)
			).fetchone()[0]
			file_dest = join(folder, basename(download.file))
			logging.debug(
				f'Moving download to final destination: {download}, Dest: {file_dest}'
			)

			if exists(file_dest):
				logging.warning(
					f'The file {file_dest} already exists; replacing with downloaded file'
				)
				remove(file_dest)

			move(download.file, file_dest)
			download.file = file_dest
		return

	@staticmethod
	def unzip_file(download) -> None:
		"Unzip the file"
		if download.file.lower().endswith('.zip'):
			unzip = get_db().execute(
				"SELECT value FROM config WHERE key = 'unzip';"
			).fetchone()[0]
			if unzip:
				unzip_volume(download.volume_id, download.file)
		return

	@staticmethod
	def delete_file(download) -> None:
		"Delete file from download folder"		
		if exists(download.file):
			remove(download.file)
		return

	@staticmethod
	def add_file_to_database(download) -> None:
		"Register file in database and match to a volume/issue"
		scan_files(Volume(download.volume_id).get_info())
		return

	@staticmethod
	def convert_file(download) -> None:
		"Convert a file into a different format based on settings"
		cursor = get_db()

		if not cursor.execute(
			"SELECT value FROM config WHERE key = 'convert' LIMIT 1;"
		).fetchone()[0]:
			return

		format_preference = cursor.execute(
			"SELECT value FROM config WHERE key = 'format_preference' LIMIT 1;"
		).fetchone()[0].split(',')
		if format_preference == ['']:
			format_preference = []
		
		if not format_preference:
			return
		
		converter = find_target_format_file(
			self.download.file,
			format_preference
		)
		if converter is not None:
			converter().convert(download.file)
		return

	@staticmethod
	def move_file_torrent(download) -> None:
		"""Move file downloaded using torrent from download folder to
		final destination"""
		PPA.move_file(download)

		cursor = get_db('dict')

		files = _extract_files_from_folder(
			download.file,
			download.volume_id
		)

		scan_files(Volume(download.volume_id).get_info())

		rename_files = cursor.execute("""
			SELECT value
			FROM config
			WHERE key = 'rename_downloaded_files'
			LIMIT 1;
		""").fetchone()[0]

		if rename_files and files:
			mass_rename(download.volume_id, filepath_filter=files)

		return

PPA = PostProcessingActions
"""Rename of PostProcessingActions to make local code less cluttered.
Advised to use the name `PostProcessingActions` outside of this file."""

class PostProcesser:
	actions_success = [
		PPA.remove_from_queue,
		PPA.add_to_history,
		PPA.move_file,
		PPA.convert_file,
		PPA.add_file_to_database,
		PPA.unzip_file
	]

	actions_canceled = [
		PPA.delete_file,
		PPA.remove_from_queue
	]

	actions_shutdown = [
		PPA.delete_file
	]

	actions_failed = [
		PPA.remove_from_queue,
		PPA.add_to_history,
		PPA.delete_file
	]

	@staticmethod
	def __run_actions(actions: list, download) -> None:
		for action in actions:
			action(download)
		return

	@classmethod
	def success(cls, download) -> None:
		logging.info(f'Postprocessing of successful download: {download.id}')
		cls.__run_actions(cls.actions_success, download)
		return

	@classmethod
	def canceled(cls, download) -> None:
		logging.info(f'Postprocessing of canceled download: {download.id}')
		cls.__run_actions(cls.actions_canceled, download)
		return

	@classmethod
	def shutdown(cls, download) -> None:
		logging.info(f'Postprocessing of shut down download: {download.id}')
		cls.__run_actions(cls.actions_shutdown, download)
		return

	@classmethod
	def failed(cls, download) -> None:
		logging.info(f'Postprocessing of failed download: {download.id}')
		cls.__run_actions(cls.actions_failed, download)
		return

class PostProcesserTorrents(PostProcesser):
	actions_success = [
		PPA.remove_from_queue,
		PPA.add_to_history,
		PPA.move_file_torrent,
		PPA.convert_file,
		PPA.unzip_file
	]

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

def _extract_files_from_folder(
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

def unzip_volume(volume_id: int, file: str=None) -> None:
	"""Get the zip files of a volume and unzip them.
	This process unzips the file, deletes the original zip file,
	deletes files not relevant for the volume, and renames them.

	Args:
		volume_id (int): The id of the volume to unzip for.
		file (str, optional): Instead of unzipping all zip files for the volume,
		only unzip the given file. Defaults to None.
	"""	
	cursor = get_db('dict')
	if file:
		logging.info(
			f'Unzipping the following file for volume {volume_id}: {file}'
		)
		files = [file]
	else:
		logging.info(f'Unzipping for volume {volume_id}')
		files = [f[0] for f in cursor.execute("""
			SELECT DISTINCT filepath
			FROM files f
			INNER JOIN issues_files if
			INNER JOIN issues i
			ON
				if.issue_id = i.id
				AND if.file_id = f.id
			WHERE
				i.volume_id = ?
				AND filepath LIKE '%.zip';
		""", (volume_id,))]

	if not files:
		return

	volume_folder = cursor.execute(
		"SELECT folder FROM volumes WHERE id = ? LIMIT 1;",
		(volume_id,)
	).fetchone()['folder']

	# All zip files gathered, now handle them one by one
	resulting_files: List[str] = []
	zip_folder = join(volume_folder, zip_extract_folder)
	for f in files:
		logging.debug(f'Unzipping {f}')
		
		# 1. Unzip
		with ZipFile(f, 'r') as zip:
			zip.extractall(zip_folder)

		# 2. Delete original file
		remove(f)

		# 3. Filter files and pull matching ones out of folder into volume folder
		resulting_files += _extract_files_from_folder(
			zip_folder,
			volume_id
		)

	# 4. Rename remaining files
	scan_files(Volume(volume_id).get_info())
	if resulting_files:
		mass_rename(volume_id, filepath_filter=resulting_files)

	return
