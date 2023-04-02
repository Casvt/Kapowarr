#-*- coding: utf-8 -*-

"""This file contains functions regarding the post processing of downloads
"""

import logging
from abc import ABC, abstractmethod
from os import remove
from os.path import basename, isfile, join
from shutil import move
from time import time

from backend.db import get_db
from backend.volumes import scan_files

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
	def __init__(self, download) -> None:
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

	def _remove_from_queue(self) -> None:
		get_db().execute(
			"DELETE FROM download_queue WHERE id = ?",
			(self.download.id,)
		)
		return

	def _add_to_history(self) -> None:
		get_db().execute(
			"""
			INSERT INTO download_history(original_link, title, downloaded_at)
			VALUES (?,?,?);
			""",
			(self.download.original_link, self.download.title, round(time()))
		)
		return
		
	def _move_file(self) -> None:
		if isfile(self.download.file):
			folder = get_db().execute(
				"SELECT folder FROM volumes WHERE id = ?",
				(self.download.volume_id,)
			).fetchone()[0]
			file_dest = join(folder, basename(self.download.file))
			if isfile(file_dest):
				remove(file_dest)
			move(self.download.file, file_dest)
			self.download.file = file_dest
		return
		
	def _delete_file(self) -> None:
		if isfile(self.download.file):
			remove(self.download.file)
	
	def _add_file_to_database(self) -> None:
		scan_files(self.download.volume_id)
		return

	def __run_actions(self, actions: list) -> None:
		for action in actions:
			action()
		return

	def short(self) -> None:
		logging.info(f'Post-download short processing: {self.download.id}')
		self.__run_actions(self.actions_short)
		return	
	
	def full(self) -> None:
		logging.info(f'Post-download processing: {self.download.id}')
		self.__run_actions(self.actions_full)
		return
		
	def error(self) -> None:
		logging.info(f'Post-download error processing: {self.download.id}')
		self.__run_actions(self.actions_error)
		return
