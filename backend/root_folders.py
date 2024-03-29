#-*- coding: utf-8 -*-

import logging
from os.path import isdir
from os.path import sep as path_sep
from sqlite3 import IntegrityError
from typing import List

from backend.custom_exceptions import (FolderNotFound, RootFolderInUse,
                                       RootFolderInvalid, RootFolderNotFound)
from backend.db import get_db
from backend.files import folder_is_inside_folder


class RootFolders:
	cache = {}

	def get_all(self, use_cache: bool=True) -> List[dict]:
		"""Get all rootfolders

		Args:
			use_cache (bool, optional): Wether or not to pull data from
			cache instead of going to the database.
				Defaults to True.

		Returns:
			List[dict]: The list of rootfolders
		"""
		if not use_cache or not self.cache:
			root_folders = get_db(dict).execute(
				"SELECT id, folder FROM root_folders;"
			)
			self.cache = {r['id']: dict(r) for r in root_folders}
		return list(self.cache.values())

	def get_one(self, root_folder_id: int, use_cache: bool=True) -> dict:
		"""Get a rootfolder based on it's id.

		Args:
			root_folder_id (int): The id of the rootfolder to get.

			use_cache (bool, optional): Wether or not to pull data from
			cache instead of going to the database.
				Defaults to True.

		Raises:
			RootFolderNotFound: The id doesn't map to any rootfolder.
				Could also be because of cache being behind database.

		Returns:
			dict: The rootfolder info
		"""
		if not use_cache or not self.cache:
			self.get_all(use_cache=False)
		root_folder = self.cache.get(root_folder_id)
		if not root_folder:
			raise RootFolderNotFound
		return root_folder

	def __getitem__(self, root_folder_id: int) -> str:
		return self.get_one(root_folder_id)['folder']

	def add(self, folder: str) -> dict:
		"""Add a rootfolder

		Args:
			folder (str): The folder to add

		Raises:
			FolderNotFound: The folder doesn't exist

		Returns:
			dict: The rootfolder info
		"""
		# Format folder and check if it exists
		logging.info(f'Adding rootfolder from {folder}')
		if not isdir(folder):
			raise FolderNotFound
		if not folder.endswith(path_sep):
			folder += path_sep

		for current_rf in self.get_all():
			if (
				folder_is_inside_folder(current_rf['folder'], folder)
				or folder_is_inside_folder(folder, current_rf['folder'])
			):
				raise RootFolderInvalid

		# Insert into database
		root_folder_id = get_db(dict).execute(
			"INSERT INTO root_folders(folder) VALUES (?)",
			(folder,)
		).lastrowid

		root_folder = self.get_one(root_folder_id, use_cache=False)

		logging.debug(f'Adding rootfolder result: {root_folder_id}')
		return root_folder

	def delete(self, id: int) -> None:
		"""Delete a rootfolder

		Args:
			id (int): The id of the rootfolder to delete

		Raises:
			RootFolderNotFound: The id doesn't map to any rootfolder
			RootFolderInUse: The rootfolder is still in use by a volume
		"""
		logging.info(f'Deleting rootfolder {id}')
		cursor = get_db()

		# Remove from database
		try:
			if not cursor.execute(
				"DELETE FROM root_folders WHERE id = ?", (id,)
			).rowcount:
				raise RootFolderNotFound
		except IntegrityError:
			raise RootFolderInUse

		self.get_all(use_cache=False)
		return
