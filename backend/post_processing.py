#-*- coding: utf-8 -*-

"""This file contains functions regarding the post processing of downloads
"""

import logging
from abc import ABC, abstractmethod
from os import remove
from os.path import basename, isfile, join
from shutil import move, rmtree
from time import time
from zipfile import ZipFile

from backend.db import get_db
from backend.files import extract_filename_data
from backend.naming import mass_rename
from backend.search import _check_matching_titles
from backend.volumes import Volume, scan_files

zip_extract_folder = '.zip_extract'

class PostProcessor(ABC):
	@abstractmethod
	def __init__(self, download):
		return
	
	def short(self) -> None:
		return
		
	def full(self) -> None:
		return
		
	def error(self) -> None:
		return

class PostProcessing(PostProcessor):
	"""For processing a file after downloading it
	"""	
	def __init__(self, download, queue: list) -> None:
		"""Setup a post processor for the download

		Args:
			download (Download): The download queue entry for which to setup the processor.
			Value should be from download.DownloadHandler.queue
			queue (List[dict]): The download queue. Value should be download.DownloadHandler.queue
		"""
		self.actions_short = [
			self._delete_file
		]
		
		self.actions_full = [
			self._remove_from_queue,
			self._add_to_history,
			self._move_file,
			self._add_file_to_database,
			self._unzip_file
		]
		
		self.actions_error = [
			self._remove_from_queue,
			self._add_to_history,
			self._delete_file
		]
		
		self.download = download
		self.queue = queue
		return

	def _remove_from_queue(self) -> None:
		"""Delete the download from the queue in the database
		"""
		for entry in self.queue:
			if entry.db_id == self.download.db_id and entry.id != self.download.id:
				break
		else:
			get_db().execute(
				"DELETE FROM download_queue WHERE id = ?",
				(self.download.db_id,)
			)
		return

	def _add_to_history(self) -> None:
		"""Add the download to history in the database
		"""
		get_db().execute(
			"""
			INSERT INTO download_history(original_link, title, downloaded_at)
			VALUES (?,?,?);
			""",
			(self.download.page_link, self.download.title, round(time()))
		)
		return
		
	def _move_file(self) -> None:
		"""Move file from download folder to final destination
		"""
		logging.debug(f'Moving download to final destination: {self.download}')
		if isfile(self.download.file):
			folder = get_db().execute(
				"SELECT folder FROM volumes WHERE id = ? LIMIT 1",
				(self.download.volume_id,)
			).fetchone()[0]
			file_dest = join(folder, basename(self.download.file))
			if isfile(file_dest):
				logging.warning(f'The file {file_dest} already exists; replacing with downloaded file')
				remove(file_dest)
			move(self.download.file, file_dest)
			self.download.file = file_dest
		return
		
	def _unzip_file(self) -> None:
		if self.download.file.lower().endswith('.zip'):
			unzip = get_db().execute("SELECT value FROM config WHERE key = 'unzip';").fetchone()[0]
			if unzip:
				unzip_volume(self.download.volume_id, self.download.file)
		return

	def _delete_file(self) -> None:
		"""Delete file from download folder
		"""		
		if isfile(self.download.file):
			remove(self.download.file)
		return
	
	def _add_file_to_database(self) -> None:
		"""Register file in database and match to a volume/issue
		"""
		scan_files(Volume(self.download.volume_id).get_info())
		return

	def __run_actions(self, actions: list) -> None:
		"""Run all actions in the list supplied

		Args:
			actions (list): A list of actions that should be run on the file
		"""		
		for action in actions:
			action()
		return

	def short(self) -> None:
		"""Process the file with the 'short'-program. Intended for when the application is shutting down.
		"""
		logging.info(f'Post-download short processing: {self.download.id}')
		self.__run_actions(self.actions_short)
		return	
	
	def full(self) -> None:
		"""Process the file with the 'full'-program. Intended for standard handling of the file.
		"""
		logging.info(f'Post-download processing: {self.download.id}')
		self.__run_actions(self.actions_full)
		return
		
	def error(self) -> None:
		"""Process the file with the 'error'-program. Intended for when the download had an error.
		"""
		logging.info(f'Post-download error processing: {self.download.id}')
		self.__run_actions(self.actions_error)
		return

def unzip_volume(volume_id: int, file: str=None) -> None:
	"""Get the zip files of a volume and unzip them.
	This process unzips the file, deletes the original zip file,
	deletes files not relevant for the volume, and renames them.

	Args:
		volume_id (int): The id of the volume to unzip for.
		file (str, optional): Instead of unzipping all zip files for the volume,
		only unzip the given file. Defaults to None.
	"""	
	cursor = get_db()
	if file:
		logging.info(f'Unzipping the following file for volume {volume_id}: {file}')
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
		
	volume_data = cursor.execute(
		"SELECT title, year, volume_number, folder FROM volumes WHERE id = ? LIMIT 1;",
		(volume_id,)
	).fetchone()
	annual = 'annual' in volume_data[0].lower()

	# All zip files gathered, now handle them one by one
	resulting_files = []
	resulting_files_append = resulting_files.append
	zip_folder = join(volume_data[3], zip_extract_folder)
	for f in files:
		logging.debug(f'Unzipping {f}')
		
		# 1. Unzip
		with ZipFile(f, 'r') as zip:
			contents = [join(zip_folder, c) for c in zip.namelist() if not c.endswith('/')]
			logging.debug(f'Zip contents: {contents}')
			zip.extractall(zip_folder)

		# 2. Delete original file
		remove(f)

		# 3. Filter non-relevant files
		rel_files = []
		rel_files_append = rel_files.append
		for c in contents:
			if 'variant cover' in c.lower():
				continue

			result = extract_filename_data(c, False)
			if (_check_matching_titles(result['series'], volume_data[0])
			and (
				# Year has to match
				(result['year'] is not None
     				and volume_data[1] - 1 <= result['year'] <= volume_data[1] + 1)
				# Or volume number
				or (result['volume_number'] is not None
					and result['volume_number'] == volume_data[2])
				# Or neither should be found (we play it safe so we keep those)
				or (result['year'] is None and result['volume_number'] is None)
			)
			and result['annual'] == annual):
				rel_files_append(c)
		logging.debug(f'Zip relevant files: {rel_files}')

		# 4. Delete non-relevant files
		for c in contents:
			if not c in rel_files:
				remove(c)

		# 5. Move remaining files to main folder and delete zip folder
		for c in rel_files:
			dest = join(volume_data[3], basename(c))
			move(c, dest)
			resulting_files_append(dest)
		rmtree(zip_folder, ignore_errors=True)

	# 6. Rename remaining files
	scan_files(Volume(volume_id).get_info())
	if resulting_files:
		mass_rename(volume_id, filepath_filter=resulting_files)

	return
