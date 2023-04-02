#-*- coding: utf-8 -*-

"""This file is for everything that has to do with the root folders
"""

import logging
from os.path import isdir
from os.path import sep as path_sep
from typing import List

from backend.custom_exceptions import (FolderNotFound, RootFolderInUse,
                                       RootFolderNotFound)
from backend.db import get_db

class RootFolders:
	cache = {}
	
	def get_all(self, use_cache: bool=True) -> List[dict]:
		if not self.cache or not use_cache:
			root_folders = get_db('dict').execute("SELECT id, folder FROM root_folders;").fetchall()
			self.cache = {r['id']: dict(r) for r in root_folders}
		return list(self.cache.values())

	def get_one(self, root_folder_id: int, use_cache: bool=True) -> dict:
		if not use_cache:
			self.get_all(use_cache=False)
		root_folder = self.cache.get(root_folder_id)
		if root_folder:
			return root_folder
		else:
			raise RootFolderNotFound
			
	def add(self, folder: str) -> dict:
		# Format folder and check if it exists
		logging.debug(f'Adding root folder from {folder}')
		if not isdir(folder):
			raise FolderNotFound
		if not folder.endswith(path_sep):
			folder += path_sep

		# Insert into database
		root_folder_id = get_db('dict').execute(
			"INSERT INTO root_folders(folder) VALUES (?)",
			(folder,)
		).lastrowid

		root_folder = self.get_one(root_folder_id, use_cache=False)

		return root_folder
		
	def delete(self, id: int) -> None:
		cursor = get_db()
		
		# Check if rootfolder isn't being used
		if cursor.execute(
			"SELECT id FROM volumes WHERE root_folder = ? LIMIT 1",
			(id,)
		).fetchone() is not None:
			raise RootFolderInUse

		# Remove from database
		if cursor.execute(
			"DELETE FROM root_folders WHERE id = ?", (id,)
		).rowcount == 0:
			raise RootFolderNotFound

		self.get_all(use_cache=False)
		return
