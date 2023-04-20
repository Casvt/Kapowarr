#-*- coding: utf-8 -*-

"""This file contains functions regarding volumes
"""

import logging
from io import BytesIO
from typing import List

from backend.comicvine import ComicVine
from backend.custom_exceptions import (IssueNotFound, VolumeAlreadyAdded, VolumeDownloadedFor,
                                       VolumeNotFound)
from backend.db import get_db
from backend.files import (create_volume_folder, delete_volume_folder,
                           move_volume_folder, scan_files)
from backend.root_folders import RootFolders


#=====================
# Main issue class
#=====================
class Issue:
	"""For representing an issue of a volume
	"""	
	def __init__(self, id: int):
		"""Initiate the representation of the issue

		Args:
			id (int): The id of the issue to represent

		Raises:
			IssueNotFound: The id doesn't map to any issue
		"""
		self.id = id
		issue_found = get_db().execute(
			"SELECT 1 FROM issues WHERE id = ? LIMIT 1",
			(id,)
		).fetchone()
		if not issue_found:
			raise IssueNotFound
		
	def get_info(self) -> dict:
		"""Get all info about the issue

		Returns:
			dict: The info about the issue
		"""
		cursor = get_db('dict')
		
		# Get issue data
		data = dict(cursor.execute(
			"""
			SELECT
				id, volume_id, comicvine_id,
				issue_number, calculated_issue_number,
				title, date, description,
				monitored
			FROM issues
			WHERE id = ?
			LIMIT 1;
			""",
			(self.id,)
		).fetchone())

		# Get all files linked to issue
		data['files'] = tuple(map(
			lambda f: f[0],
			cursor.execute(
				"""
				SELECT filepath
				FROM files
				INNER JOIN issues_files
				ON file_id = id
				WHERE issue_id = ?;
				""",
				(self.id,)
			).fetchall()
		))
		data['monitored'] = data['monitored'] == 1
		return data
		
	def monitor(self) -> None:
		"""Set the issue to "monitored"
		"""		
		logging.info(f'Setting issue {self.id} to monitored')
		get_db().execute(
			"UPDATE issues SET monitored = 1 WHERE id = ?",
			(self.id,)
		)
		return
		
	def unmonitor(self) -> None:
		"""Set the issue to "unmonitored"
		"""		
		logging.info(f'Setting issue {self.id} to unmonitored')
		get_db().execute(
			"UPDATE issues SET monitored = 0 WHERE id = ?",
			(self.id,)
		)
		return

#=====================
# Main volume class
#=====================
class Volume:
	"""For representing a volume in the library
	"""	
	def __init__(self, id: int):
		"""Initiate the representation of the volume

		Args:
			id (int): The id of the volume

		Raises:
			VolumeNotFound: The id doesn't map to any volume
		"""	
		self.id = id
		volume_found = get_db().execute(
			"SELECT 1 FROM volumes WHERE id = ? LIMIT 1",
			(id,)
		).fetchone()

		if not volume_found:
			raise VolumeNotFound

	def get_info(self, complete: bool=True) -> dict:
		"""Get (all) info about the volume

		Args:
			complete (bool, optional): Wether or not to also get the issue info of the volume. Defaults to True.

		Returns:
			dict: The info of the volume
		"""	
		cursor = get_db('dict')

		# Get volume info
		cursor.execute("""
			SELECT
				id, comicvine_id,
				title, year, publisher,
				volume_number, description,
				monitored,
				folder, root_folder,
				(
					SELECT COUNT(*)
					FROM issues
					WHERE volume_id = volumes.id
				) AS issue_count,
				(
					SELECT COUNT(DISTINCT issue_id)
					FROM issues i
					INNER JOIN issues_files if
					ON i.id = if.issue_id
					WHERE volume_id = volumes.id
				) AS issues_downloaded
			FROM volumes
			WHERE id = ?
			LIMIT 1
		""", (self.id,))
		volume_info = dict(cursor.fetchone())
		volume_info['monitored'] = volume_info['monitored'] == 1
		volume_info['cover'] = f'/api/volumes/{volume_info["id"]}/cover'

		if complete:
			# Get issue info
			issues = list(map(dict, cursor.execute("""
				SELECT
					id, volume_id, comicvine_id,
					issue_number, calculated_issue_number,
					title, date, description,
					monitored
				FROM issues
				WHERE volume_id = ?
				ORDER BY date, calculated_issue_number
			""", (self.id,)).fetchall()))
			for issue in issues:
				issue['monitored'] = issue['monitored'] == 1
				cursor.execute("""
					SELECT f.filepath
					FROM issues_files if
					INNER JOIN files f
					ON if.file_id = f.id
					WHERE if.issue_id = ?;
					""",
					(issue['id'],)
				)
				issue['files'] = list(f[0] for f in cursor.fetchall())
			volume_info['issues'] = issues
		return volume_info

	def get_cover(self) -> BytesIO:
		"""Get the cover image of the volume

		Returns:
			BytesIO: The cover image of the volume
		"""
		cover = get_db().execute(
			"SELECT cover FROM volumes WHERE id = ? LIMIT 1",
			(self.id,)
		).fetchone()[0]
		return BytesIO(cover)

	def edit(self, edits: dict) -> dict:
		"""Edit the volume

		Args:
			edits (dict): The keys and their new values for the volume settings (`monitor` and `root_folder_id` supported)

		Returns:
			dict: The new info of the volume
		"""
		logging.debug(f'Editing volume {self.id}: {edits}')
		monitored = edits.get('monitor')
		if monitored == True:
			self._monitor()
		elif monitored == False:
			self._unmonitor()
		
		root_folder_id = edits.get('root_folder_id')
		if root_folder_id:
			self._edit_root_folder(root_folder_id)

		return self.get_info()

	def _monitor(self) -> None:
		"""Set the volume to "monitored"
		"""
		logging.info(f'Setting volume {self.id} to monitored')
		get_db().execute(
			"UPDATE volumes SET monitored = 1 WHERE id = ?",
			(self.id,)
		)
		return

	def _unmonitor(self) -> None:
		"""Set the volume to "unmonitored"
		"""
		logging.info(f'Setting volume {self.id} to unmonitored')
		get_db().execute(
			"UPDATE volumes SET monitored = 0 WHERE id = ?",
			(self.id,)
		)
		return

	def _edit_root_folder(self, root_folder_id: int) -> None:
		"""Change the root folder of the volume

		Args:
			root_folder_id (int): The id of the new root folder to move the volume to
		"""
		# Check that current root folder and new root folder aren't the same
		current_root_folder_id, folder = get_db().execute(
			"SELECT root_folder, folder FROM volumes WHERE id = ? LIMIT 1",
			(self.id,)
		).fetchone()
		if current_root_folder_id == root_folder_id:
			return
		logging.info(f'Changing root folder of volume {self.id} from {current_root_folder_id} to {root_folder_id}')

		# Get paths and move
		rf = RootFolders()
		current_root_folder = rf.get_one(current_root_folder_id)['folder']
		new_root_folder = rf.get_one(root_folder_id)['folder']
		new_folder = move_volume_folder(folder, current_root_folder, new_root_folder)

		# Set new location in DB		
		get_db().execute(
			"UPDATE volumes SET folder = ?, root_folder = ? WHERE id = ?",
			(new_folder, root_folder_id, self.id)
		)
		return

	def delete(self, delete_folder: bool=False) -> None:
		"""Delete the volume from the library

		Args:
			delete_folder (bool, optional): Also delete the volume folder and it's contents. Defaults to False.

		Raises:
			VolumeDownloadedFor: There is a download in the queue for the volume
			
		"""
		logging.info(f'Deleting volume {self.id} with delete_folder set to {delete_folder}')
		cursor = get_db()

		# Delete volume folder
		if delete_folder:
			delete_volume_folder(self.id)

		# Check if nothing is downloading for the volume
		downloading_for_volume = cursor.execute("""
			SELECT 1
			FROM download_queue
			WHERE volume_id = ?
			LIMIT 1;
		""", (self.id,)).fetchone()
		if downloading_for_volume:
			raise VolumeDownloadedFor(self.id)

		# Delete file entries
		# ON DELETE CASCADE will take care of issues_files
		cursor.execute(
			"""
			DELETE FROM files
			WHERE id IN (
				SELECT id
				FROM issues
				WHERE volume_id = ?
			);
			""",
			(self.id,)
		)
		# Delete metadata entries
		# ON DELETE CASCADE will take care of issues
		cursor.execute("DELETE FROM volumes WHERE id = ?", (self.id,))

		return

def refresh_and_scan_volume(volume_id: int) -> None:
	"""Refresh and scan a volume

	Args:
		volume_id (int): The id of the volume for which to perform the action
	"""
	cursor = get_db()

	comicvine_id = str(cursor.execute(
		"SELECT comicvine_id FROM volumes WHERE id = ? LIMIT 1;",
		(volume_id,)
	).fetchone()[0])

	# Get volume info
	volume_data = ComicVine().fetch_volume(comicvine_id)

	cursor.execute(
		"""
		UPDATE volumes
		SET
			title = ?,
			year = ?,
			publisher = ?,
			volume_number = ?,
			description = ?,
			cover = ?
		WHERE id = ?;
		""",
		(
			volume_data['title'],
			volume_data['year'],
			volume_data['publisher'],
			volume_data['volume_number'],
			volume_data['description'],
			volume_data['cover'],
			volume_id
		)
	)

	# Scan for files
	scan_files(Volume(volume_id).get_info())

	volume_data['issues'] = map(
		lambda i: (
			i['issue_number'],
			i['calculated_issue_number'],
			i['title'],
			i['date'],
			i['description'],
			i['comicvine_id']
		),
		volume_data['issues']
	)

	cursor.executemany("""
		UPDATE issues
		SET
			issue_number = ?,
			calculated_issue_number = ?,
			title = ?,
			date = ?,
			description = ?
		WHERE
			comicvine_id = ?;
	""", volume_data['issues'])

	return

#=====================
# Library class
#=====================
class Library:
	sorting_orders = {
		'title': 'title, year, volume_number',
		'year': 'year, title, volume_number',
		'volume_number': 'volume_number, title, year',
		'recently_added': 'id DESC, title, year, volume_number'
	}
	
	def __format_lib_output(self, library: List[dict]) -> List[dict]:
		"""Format the library entries for API response

		Args:
			library (List[dict]): The unformatted library entries list

		Returns:
			List[dict]: The formatted library list
		"""
		for entry in library:
			entry['monitored'] = entry['monitored'] == 1
			entry['cover'] = f'/api/volumes/{entry["id"]}/cover'
		return library
	
	def get_volumes(self, sort: str='title') -> List[dict]:
		"""Get all volumes in the library

		Args:
			sort (str, optional): How to sort the list. `title`, `year`, `volume_number` and `recently_added` allowed. Defaults to 'title'.

		Returns:
			List[dict]: The list of volumes in the library.
		"""		
		# Determine sorting order
		sort = self.sorting_orders[sort]

		# Fetch all volumes
		volumes = list(map(dict, get_db('dict').execute(f"""
			SELECT
				id, comicvine_id,
				title, year, publisher,
				volume_number, description,
				monitored,
				(
					SELECT COUNT(*)
					FROM issues
					WHERE volume_id = volumes.id
				) AS issue_count,
				(
					SELECT COUNT(DISTINCT issue_id)
					FROM issues i
					INNER JOIN issues_files if
					ON i.id = if.issue_id
					WHERE volume_id = volumes.id
				) AS issues_downloaded
			FROM volumes
			ORDER BY {sort};
		""").fetchall()))

		volumes = self.__format_lib_output(volumes)
		
		return volumes
		
	def search(self, query: str, sort: str='title') -> List[dict]:
		"""Search in the library with a query

		Args:
			query (str): The query to search with
			sort (str, optional): How to sort the list. `title`, `year`, `volume_number` and `recently_added` allowed. Defaults to 'title'.

		Returns:
			List[dict]: The resulting list of matching volumes in the library
		"""
		volumes = list(filter(
			lambda v: query.lower() in v['title'].lower(),
			self.get_volumes(sort)
		))
		
		return volumes

	def get_volume(self, volume_id: int) -> Volume:
		"""Get a volumes.Volume instance of a volume in the library

		Args:
			volume_id (int): The id of the volume

		Raises:
			VolumeNotFound: The id doesn't map to any volume in the library
			
		Returns:
			Volume: The volumes.Volume instance representing the volume with the given id
		"""
		return Volume(volume_id)

	def get_issue(self, issue_id: int) -> Issue:
		"""Get a volumes.Issue instance of an issue in the library

		Args:
			issue_id (int): The id of the issue

		Raises:
			IssueNotFound: The id doesn't map to any issue in the library
			
		Returns:
			Issue: The volumes.Issue instance representing the issue with the given id
		"""		
		return Issue(issue_id)
		
	def add(self, comicvine_id: str, root_folder_id: int, monitor: bool=True) -> int:
		"""Add a volume to the library

		Args:
			comicvine_id (str): The ComicVine id of the volume
			root_folder_id (int): The id of the rootfolder in which the volume folder will be
			monitor (bool, optional): Wether or not to mark the volume as monitored. Defaults to True.

		Raises:
			VolumeAlreadyAdded: The volume already exists in the library

		Returns:
			int: The new id of the volume
		"""
		logging.debug(f'Adding a volume to the library: CV ID {comicvine_id}, RF ID {root_folder_id}, Monitor {monitor}')
		cursor = get_db()

		# Check if volume isn't already added
		already_exists = cursor.execute(
			"SELECT 1 FROM volumes WHERE comicvine_id = ? LIMIT 1",
			(comicvine_id,)
		).fetchone()
		if already_exists:
			raise VolumeAlreadyAdded

		# Check if root folder exists
		# Raises RootFolderNotFound when id is invalid
		root_folder = RootFolders().get_one(root_folder_id, use_cache=False)['folder']

		# Get volume info
		volume_data = ComicVine().fetch_volume(comicvine_id)
		volume_data['monitored'] = monitor
		volume_data['root_folder'] = root_folder_id

		# Insert volume
		cursor.execute(
			"""
			INSERT INTO volumes(
				comicvine_id,
				title,
				year,
				publisher,
				volume_number,
				description,
				cover,
				monitored,
				root_folder
			) VALUES (
				?, ?, ?, ?, ?, ?, ?, ?, ?
			);
			""",
			(
				volume_data['comicvine_id'],
				volume_data['title'],
				volume_data['year'],
				volume_data['publisher'],
				volume_data['volume_number'],
				volume_data['description'],
				volume_data['cover'],
				volume_data['monitored'],
				volume_data['root_folder']
			)
		)
		volume_id = cursor.lastrowid
		
		# Setup folder
		create_volume_folder(root_folder, volume_id)

		# Prepare and insert issues
		issue_list = map(
			lambda i: (
				volume_id,
				i['comicvine_id'],
				i['issue_number'],
				i['calculated_issue_number'],
				i['title'],
				i['date'],
				i['description'],
				True
			),
			volume_data['issues']
		)
		
		cursor.executemany("""
			INSERT INTO issues(
				volume_id,
				comicvine_id,
				issue_number,
				calculated_issue_number,
				title,
				date,
				description,
				monitored
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		""", issue_list)

		logging.info(f'Added volume with comicvine id {comicvine_id} and id {volume_id}')
		return volume_id

def search_volumes(query: str) -> List[dict]:
	"""Search for a volume in the ComicVine database

	Args:
		query (str): The query to search with

	Raises:
		InvalidComicVineApiKey: The ComicVine API key is not set or is invalid
		
	Returns:
		List[dict]: The list with search results
	"""
	return ComicVine().search_volumes(query)
