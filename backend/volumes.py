#-*- coding: utf-8 -*-

"""This file contains functions regarding volumes
"""

import logging
from io import BytesIO
from os.path import relpath
from re import IGNORECASE, compile
from time import time
from typing import Dict, List, Union

from backend.comicvine import ComicVine
from backend.custom_exceptions import (IssueNotFound, VolumeAlreadyAdded,
                                       VolumeDownloadedFor, VolumeNotFound)
from backend.db import get_db
from backend.files import (create_volume_folder, delete_volume_folder,
                           move_volume_folder, scan_files)
from backend.root_folders import RootFolders
from frontend.ui import ui_vars

os_regex = compile(r'(?<!>)\bone[\- ]?shot\b(?!<)', IGNORECASE)
hc_regex = compile(r'(?<!>)\bhard[\- ]?cover\b(?!<)', IGNORECASE)
vol_regex = compile(r'^volume\.?\s\d+$', IGNORECASE)
def determine_special_version(
	volume_title: str,
	volume_description: str,
	issue_titles: List[str]
) -> Union[str, None]:
	"""Determine if a volume is a special version.

	Args:
		volume_title (str): The title of the volume.
		volume_description (str): The description of the volume.
		issue_titles (List[str]): The titles of all issues in the volume.

	Returns:
		Union[str, None]: `tpb`, `one-shot`, `hard-cover`, `volume-as-issue`
		or `None`.
	"""
	if os_regex.search(volume_title):
		return 'one-shot'

	if issue_titles:
		if (issue_titles[0] or '').lower() == 'hc':
			return 'hard-cover'

		if all(
			vol_regex.search(title or '')
			for title in issue_titles
		):
			return 'volume-as-issue'

	if volume_description and len(volume_description.split('. ')) == 1:
		# Description is only one sentence, so it's allowed to
		# look in description for special version.
		# Only one sentence is allowed because otherwise the description
		# could be referencing a special version that isn't this one,
		# leading to a false hit.
		if os_regex.search(volume_description):
			return 'one-shot'
		
		if hc_regex.search(volume_description):
			return 'hard-cover'

	if len(issue_titles) == 1:
		return 'tpb'

	return None

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
		)
		if not (1,) in issue_found:
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
		data['files'] = [
			f[0] for f in cursor.execute(
				"""
				SELECT filepath
				FROM files
				INNER JOIN issues_files
				ON file_id = id
				WHERE issue_id = ?
				ORDER BY filepath;
				""",
				(self.id,)
			)
		]
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
		)

		if not (1,) in volume_found:
			raise VolumeNotFound

	def get_info(self, complete: bool=True) -> dict:
		"""Get (all) info about the volume

		Args:
			complete (bool, optional): Whether or not to also get the info of
			the issues inside the volume.
				Defaults to True.

		Returns:
			dict: The info of the volume
		"""	
		cursor = get_db('dict')

		cursor.execute("""
			SELECT
				v.id, comicvine_id,
				title, year, publisher,
				volume_number, special_version,
				description, monitored,
				v.folder, root_folder,
				rf.folder AS root_folder_path,
				(
					SELECT COUNT(*)
					FROM issues
					WHERE volume_id = v.id
				) AS issue_count,
				(
					SELECT COUNT(DISTINCT issue_id)
					FROM issues i
					INNER JOIN issues_files if
					ON i.id = if.issue_id
					WHERE volume_id = v.id
				) AS issues_downloaded
			FROM volumes v
			INNER JOIN root_folders rf
			ON v.root_folder = rf.id
			WHERE v.id = ?
			LIMIT 1;
		""", (self.id,))
		volume_info = dict(cursor.fetchone())
		volume_info['monitored'] = volume_info['monitored'] == 1
		volume_info['cover'] = f'{ui_vars["url_base"]}/api/volumes/{volume_info["id"]}/cover'
		volume_info['volume_folder'] = relpath(
			volume_info['folder'],
			volume_info['root_folder_path']
		)
		del volume_info['root_folder_path']

		if complete:
			# Get issue info
			issues = [
				dict(i) for i in cursor.execute("""
					SELECT
						id, volume_id, comicvine_id,
						issue_number, calculated_issue_number,
						title, date, description,
						monitored
					FROM issues
					WHERE volume_id = ?
					ORDER BY date, calculated_issue_number
					""",
					(self.id,)
				)
			]
			for issue in issues:
				issue['monitored'] = issue['monitored'] == 1
				issue['files'] = [
					f[0] for f in cursor.execute("""
						SELECT f.filepath
						FROM issues_files if
						INNER JOIN files f
						ON if.file_id = f.id
						WHERE if.issue_id = ?
						ORDER BY f.filepath;
						""",
						(issue['id'],)
					)
				]
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
			edits (dict): The keys and their new values for the volume settings
			(`monitor` and `new_root_folder` + `new_volume_folder` supported)

		Returns:
			dict: The new info of the volume
		"""
		logging.debug(f'Editing volume {self.id}: {edits}')
		monitored = edits.get('monitor')
		if monitored == True:
			self._monitor()
		elif monitored == False:
			self._unmonitor()

		new_root_folder = edits.get('new_root_folder')
		new_volume_folder = edits.get('new_volume_folder')
		if new_root_folder and (new_volume_folder or not new_volume_folder):
			self._edit_folder(new_root_folder, new_volume_folder)

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

	def _edit_folder(self, new_root_folder: int, new_volume_folder: str) -> None:
		"""Change the root folder of the volume

		Args:
			new_root_folder (int): The id of the new root folder to move the volume to
			new_volume_folder (str): The new volume folder to move the volume to
		"""
		current_root_folder, folder = get_db().execute(
			"SELECT root_folder, folder FROM volumes WHERE id = ? LIMIT 1",
			(self.id,)
		).fetchone()

		new_folder = move_volume_folder(
			self.id,
			new_root_folder,
			new_volume_folder
		)
		if current_root_folder == new_root_folder and folder == new_folder:
			return

		get_db().execute(
			"UPDATE volumes SET folder = ?, root_folder = ? WHERE id = ?",
			(new_folder, new_root_folder, self.id)
		)
		return

	def delete(self, delete_folder: bool=False) -> None:
		"""Delete the volume from the library

		Args:
			delete_folder (bool, optional): Also delete the volume folder and
			it's contents.
				Defaults to False.

		Raises:
			VolumeDownloadedFor: There is a download in the queue for the volume
			
		"""
		logging.info(f'Deleting volume {self.id} with delete_folder set to {delete_folder}')
		cursor = get_db()

		# Check if nothing is downloading for the volume
		downloading_for_volume = cursor.execute("""
			SELECT 1
			FROM download_queue
			WHERE volume_id = ?
			LIMIT 1;
		""", (self.id,)).fetchone()
		if downloading_for_volume:
			raise VolumeDownloadedFor(self.id)

		if delete_folder:
			delete_volume_folder(self.id)

		# Delete file entries
		# ON DELETE CASCADE will take care of issues_files
		cursor.execute(
			"""
			DELETE FROM files
			WHERE id IN (
				SELECT DISTINCT file_id
				FROM issues_files
				INNER JOIN issues
				ON issues_files.issue_id = issues.id
				WHERE volume_id = ?
			);
			""",
			(self.id,)
		)
		# Delete metadata entries
		# ON DELETE CASCADE will take care of issues
		cursor.execute("DELETE FROM volumes WHERE id = ?", (self.id,))

		return

def refresh_and_scan(volume_id: int=None) -> None:
	"""Refresh and scan one or more volumes

	Args:
		volume_id (int, optional): The id of the volume if it is desired to
		only refresh and scan one. If left to `None`, all volumes are refreshed
		and scanned.
			Defaults to None.
	"""
	cursor = get_db()
	cv = ComicVine()

	one_day_ago = round(time()) - 86400
	if volume_id:
		ids = dict(cursor.execute(
			"SELECT comicvine_id, id FROM volumes WHERE id = ? LIMIT 1;",
			(volume_id,)
		))
	else:
		ids = dict(cursor.execute("""
			SELECT comicvine_id, id
			FROM volumes
			WHERE last_cv_fetch <= ?
			ORDER BY last_cv_fetch ASC;
			""",
			(one_day_ago,)
		))
	str_ids = [str(i) for i in ids]

	# Update volumes
	volume_datas = cv.fetch_volumes(str_ids)
	update_volumes = ((
				volume_data['title'],
				volume_data['year'],
				volume_data['publisher'],
				volume_data['volume_number'],
				volume_data['description'],
				volume_data['cover'],
				one_day_ago + 86400,

				ids[volume_data['comicvine_id']]
		)
		for volume_data in volume_datas
	)
	cursor.executemany(
		"""
		UPDATE volumes
		SET
			title = ?,
			year = ?,
			publisher = ?,
			volume_number = ?,
			description = ?,
			cover = ?,
			last_cv_fetch = ?
		WHERE id = ?;
		""",
		update_volumes
	)
	cursor.connection.commit()
		
	# Update issues
	issue_datas = cv.fetch_issues([str(v['comicvine_id']) for v in volume_datas])
	issue_updates = ((
			ids[issue_data['volume_id']],
			issue_data['comicvine_id'],
			issue_data['issue_number'],
			issue_data['calculated_issue_number'],
			issue_data['title'],
			issue_data['date'],
			issue_data['description'],
			True,
			
			issue_data['issue_number'],
			issue_data['calculated_issue_number'],
			issue_data['title'],
			issue_data['date'],
			issue_data['description']
		)
		for issue_data in issue_datas
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
		ON CONFLICT(comicvine_id) DO
		UPDATE
		SET
			issue_number = ?,
			calculated_issue_number = ?,
			title = ?,
			date = ?,
			description = ?;
	""", issue_updates)

	cursor.connection.commit()

	# Scan for files
	if volume_id:
		scan_files(Volume(volume_id).get_info())
	else:
		cursor2 = get_db(temp=True)
		cursor2.execute("SELECT id FROM volumes;")
		for volume in cursor2:
			scan_files(Volume(volume[0]).get_info())
		cursor2.connection.close()

	return

#=====================
# Library class
#=====================
class Library:
	sorting_orders = {
		'title': 'title, year, volume_number',
		'year': 'year, title, volume_number',
		'volume_number': 'volume_number, title, year',
		'recently_added': 'id DESC, title, year, volume_number',
		'publisher': 'publisher, title, year, volume_number'
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
			entry['cover'] = f'{ui_vars["url_base"]}/api/volumes/{entry["id"]}/cover'
		return library
	
	def get_volumes(self, sort: str='title') -> List[dict]:
		"""Get all volumes in the library

		Args:
			sort (str, optional): How to sort the list.
			`title`, `year`, `volume_number`, `recently_added` and `publisher` allowed.
				Defaults to 'title'.

		Returns:
			List[dict]: The list of volumes in the library.
		"""		
		sort = self.sorting_orders[sort]

		volumes = [
			dict(v) for v in get_db('dict').execute(f"""
				WITH
					vol_issues AS (
						SELECT id, monitored
						FROM issues
						WHERE volume_id = volumes.id
					),
					issues_with_files AS (
						SELECT DISTINCT issue_id, monitored
						FROM issues i
						INNER JOIN issues_files if
						ON i.id = if.issue_id
						WHERE volume_id = volumes.id
					)
				SELECT
					id, comicvine_id,
					title, year, publisher,
					volume_number, description,
					monitored,
					(
						SELECT COUNT(id) FROM vol_issues
					) AS issue_count,
					(
						SELECT COUNT(id) FROM vol_issues WHERE monitored = 1
					) AS issue_count_monitored,
					(
						SELECT COUNT(issue_id) FROM issues_with_files
					) AS issues_downloaded,
					(
						SELECT COUNT(issue_id) FROM issues_with_files WHERE monitored = 1
					) AS issues_downloaded_monitored
				FROM volumes
				ORDER BY {sort};
				"""
			)
		]

		volumes = self.__format_lib_output(volumes)
		
		return volumes
		
	def search(self, query: str, sort: str='title') -> List[dict]:
		"""Search in the library with a query

		Args:
			query (str): The query to search with
			sort (str, optional): How to sort the list.
			`title`, `year`, `volume_number`, `recently_added` and `publisher` allowed.
				Defaults to 'title'.

		Returns:
			List[dict]: The resulting list of matching volumes in the library
		"""
		volumes = [
			v
			for v in self.get_volumes(sort)
			if query.lower() in v['title'].lower()
		]
		
		return volumes

	def get_volume(self, volume_id: int) -> Volume:
		"""Get a volumes.Volume instance of a volume in the library

		Args:
			volume_id (int): The id of the volume

		Raises:
			VolumeNotFound: The id doesn't map to any volume in the library
			
		Returns:
			Volume: The `volumes.Volume` instance representing the volume
			with the given id.
		"""
		return Volume(volume_id)

	def get_issue(self, issue_id: int) -> Issue:
		"""Get a volumes.Issue instance of an issue in the library

		Args:
			issue_id (int): The id of the issue

		Raises:
			IssueNotFound: The id doesn't map to any issue in the library
			
		Returns:
			Issue: The `volumes.Issue` instance representing the issue
			with the given id.
		"""		
		return Issue(issue_id)
		
	def add(self,
		comicvine_id: str,
		root_folder_id: int,
		monitor: bool=True,
		volume_folder: str=None
	) -> int:
		"""Add a volume to the library

		Args:
			comicvine_id (str): The ComicVine id of the volume

			root_folder_id (int): The id of the rootfolder in which
			the volume folder will be.

			monitor (bool, optional): Whether or not to mark the volume as monitored.
				Defaults to True.

			volume_folder (str, optional): Custom volume folder.
				Defaults to None.

		Raises:
			RootFolderNotFound: The root folder with the given id was not found
			VolumeAlreadyAdded: The volume already exists in the library
			CVRateLimitReached: The ComicVine API rate limit is reached

		Returns:
			int: The new id of the volume
		"""
		logging.debug(
			'Adding a volume to the library: ' +
			f'CV ID {comicvine_id}, RF ID {root_folder_id}, Monitor {monitor}, VF {volume_folder}'
		)
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
		root_folder = RootFolders().get_one(root_folder_id)['folder']

		volume_data = ComicVine().fetch_volume(comicvine_id)
		volume_data['monitored'] = monitor
		volume_data['root_folder'] = root_folder_id
		
		special_version = determine_special_version(
			volume_data['title'],
			volume_data['description'],
			tuple(i['title'] for i in volume_data['issues'])
		)

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
				root_folder,
				custom_folder,
				last_cv_fetch,
				special_version
			) VALUES (
				?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
				volume_data['root_folder'],
				int(volume_folder is not None),
				round(time()),
				special_version
			)
		)
		volume_id = cursor.lastrowid

		create_volume_folder(root_folder, volume_id, volume_folder)

		# Prepare and insert issues
		issue_list = (
			(
				volume_id,
				i['comicvine_id'],
				i['issue_number'],
				i['calculated_issue_number'],
				i['title'],
				i['date'],
				i['description'],
				True
			)
			for i in volume_data['issues']
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

	def get_stats(self) -> Dict[str, int]:
		cursor = get_db('dict')
		cursor.execute("""
			WITH v_stats AS (
				SELECT
					COUNT(*) AS volumes,
					SUM(volumes.monitored) AS monitored
				FROM volumes
			), i_stats AS (
				SELECT
					COUNT(DISTINCT issues.id) AS issues,
					COUNT(DISTINCT issues_files.issue_id) AS downloaded_issues
				FROM issues
				LEFT JOIN issues_files
				ON issues.id = issues_files.issue_id
			)
			SELECT
				volumes,
				monitored,
				volumes - monitored AS unmonitored,
				issues, 
				downloaded_issues,
				COUNT(files.id) AS files, 
				SUM(files.size) AS total_file_size
			FROM
				v_stats,
				i_stats,
				files;
		""")
		return dict(cursor.fetchone())

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
