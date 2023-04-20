#-*- coding: utf-8 -*-

"""This file contains functions regarding the post processing of downloads
"""

import logging
from abc import ABC, abstractmethod
from os import remove
from os.path import basename, isfile, join
from shutil import move
from time import time
from typing import List

from backend.db import get_db
from backend.volumes import Volume, scan_files


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
	def __init__(self, download: dict, queue: List[dict]) -> None:
		"""Setup a post processor for the download

		Args:
			download (dict): The download queue entry for which to setup the processor.
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
			self._add_file_to_database
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
			if entry['db_id'] == self.download['db_id'] and entry['id'] != self.download['id']:
				break
		else:
			get_db().execute(
				"DELETE FROM download_queue WHERE id = ?",
				(self.download['db_id'],)
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
			(self.download['original_link'], self.download['instance'].title, round(time()))
		)
		return
		
	def _move_file(self) -> None:
		"""Move file from download folder to final destination
		"""
		logging.debug(f'Moving download to final destination: {self.download}')
		if isfile(self.download['instance'].file):
			folder = get_db().execute(
				"SELECT folder FROM volumes WHERE id = ? LIMIT 1",
				(self.download['volume_id'],)
			).fetchone()[0]
			file_dest = join(folder, basename(self.download['instance'].file))
			if isfile(file_dest):
				remove(file_dest)
			move(self.download['instance'].file, file_dest)
			self.download['instance'].file = file_dest
		return
		
	def _delete_file(self) -> None:
		"""Delete file from download folder
		"""		
		if isfile(self.download['instance'].file):
			remove(self.download['instance'].file)
	
	def _add_file_to_database(self) -> None:
		"""Register file in database and match to a volume/issue
		"""
		scan_files(Volume(self.download['volume_id']).get_info())
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
		logging.info(f'Post-download short processing: {self.download["id"]}')
		self.__run_actions(self.actions_short)
		return	
	
	def full(self) -> None:
		"""Process the file with the 'full'-program. Intended for standard handling of the file.
		"""
		logging.info(f'Post-download processing: {self.download["id"]}')
		self.__run_actions(self.actions_full)
		return
		
	def error(self) -> None:
		"""Process the file with the 'error'-program. Intended for when the download had an error.
		"""
		logging.info(f'Post-download error processing: {self.download["id"]}')
		self.__run_actions(self.actions_error)
		return
