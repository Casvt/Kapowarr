#-*- coding: utf-8 -*-

"""This file contains functions regarding volumes
"""

import logging
from io import BytesIO
from typing import List

from backend.comicvine import ComicVine
from backend.custom_exceptions import (IssueNotFound, VolumeAlreadyAdded,
                                       VolumeNotFound)
from backend.db import get_db
from backend.files import (create_volume_folder, delete_volume_folder,
                           move_volume_folder, scan_files)
from backend.root_folders import RootFolders

#=====================
# Main issue class
#=====================
class Issue:
	def __init__(self, id: int):
		self.id = id
		
	def get_info(self) -> dict:
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
				SELECT
					filepath
				FROM files, issues_files
				WHERE
					issue_id = ?
					AND file_id = id;
				""",
				(self.id,)
			).fetchall()
		))
		data['monitored'] = data['monitored'] == 1
		return data
		
	def monitor(self) -> None:
		get_db().execute(
			"UPDATE issues SET monitored = 1 WHERE id = ?",
			(self.id,)
		)
		logging.info(f'Issue {self.id} set to monitored')
		return
		
	def unmonitor(self) -> None:
		get_db().execute(
			"UPDATE issues SET monitored = 0 WHERE id = ?",
			(self.id,)
		)
		logging.info(f'Issue {self.id} set to unmonitored')
		return

#=====================
# Main volume class
#=====================
class Volume:
	def __init__(self, id: int):
		self.id = id

	def get_info(self, complete: bool=True) -> dict:
		cursor = get_db('dict')

		# Get volume info
		cursor.execute("""
			SELECT
				id, comicvine_id,
				title, year, publisher,
				volume_number, description,
				monitored, folder, root_folder
			FROM volumes
			WHERE id = ?
			LIMIT 1
		""", (self.id,))
		volume_info = dict(cursor.fetchone())
		volume_info['monitored'] = volume_info['monitored'] == 1
		volume_info['cover'] = f'/api/volumes/{volume_info["id"]}/cover'

		if complete:
			# Get issue info
			cursor.execute("""
				SELECT
					id, volume_id, comicvine_id,
					issue_number, calculated_issue_number,
					title, date, description,
					monitored
				FROM issues
				WHERE volume_id = ?
				ORDER BY date, calculated_issue_number
			""", (self.id,))
			issues = cursor.fetchall()
			for issue_index, issue in enumerate(issues):
				issue = dict(issue)
				issue['monitored'] = issue['monitored'] == 1
				cursor.execute("""
					SELECT f.filepath
					FROM
						issues_files AS if,
						files AS f
					WHERE
						if.file_id = f.id
						AND if.issue_id = ?;
					""",
					(issue['id'],)
				)
				issue['files'] = list(f[0] for f in cursor.fetchall())

				issues[issue_index] = issue
			volume_info['issues'] = issues
		return volume_info

	def get_cover(self) -> BytesIO:
		cover = get_db().execute(
			"SELECT cover FROM volumes WHERE id = ?",
			(self.id,)
		).fetchone()[0]
		return BytesIO(cover)

	def edit(self, edits: dict) -> dict:
		monitored = edits.get('monitor')
		if monitored == True:
			self._monitor()
		elif monitored == False:
			self._unmonitor()
		
		root_folder_id = edits.get('root_folder_id')
		if root_folder_id is not None:
			self._edit_root_folder(root_folder_id)

		return self.get_info()

	def _monitor(self) -> None:
		get_db().execute(
			"UPDATE volumes SET monitored = 1 WHERE id = ?",
			(self.id,)
		)
		logging.info(f'Volume {self.id} set to monitored')
		return

	def _unmonitor(self) -> None:
		get_db().execute(
			"UPDATE volumes SET monitored = 0 WHERE id = ?",
			(self.id,)
		)
		logging.info(f'Volume {self.id} set to unmonitored')
		return

	def _edit_root_folder(self, root_folder_id: int) -> None:
		# Check that current root folder and new root folder aren't the same
		current_root_folder_id, folder = get_db().execute(
			"SELECT root_folder, folder FROM volumes WHERE id = ?",
			(self.id,)
		).fetchone()
		if current_root_folder_id == root_folder_id:
			return

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
		logging.info(f'Volume {self.id} changed root folder from {current_root_folder_id} to {root_folder_id}')
		return

	def delete(self, delete_folder: bool=False) -> None:
		cursor = get_db()

		# Delete volume folder
		if delete_folder == True:
			delete_volume_folder(self.id)

		# Delete file entries
		file_ids = cursor.execute(
			"""
			SELECT DISTINCT file_id
			FROM issues_files
			WHERE issue_id IN (
				SELECT id
				FROM issues
				WHERE volume_id = ?
			);
			""",
			(self.id,)
		).fetchall()
		cursor.executemany(
			"DELETE FROM issues_files WHERE file_id = ?;",
			file_ids
		)
		cursor.executemany(
			"DELETE FROM files WHERE id = ?;",
			file_ids
		)
		# Delete metadata entries
		cursor.execute("DELETE FROM issues WHERE volume_id = ?", (self.id,))
		cursor.execute("DELETE FROM volumes WHERE id = ?", (self.id,))

		logging.info(f'Volume {self.id} deleted with delete_folder set to {delete_folder}')
		return

def refresh_and_scan_volume(volume_id: int) -> None:
	cursor = get_db()

	comicvine_id = str(cursor.execute(
		"""
		SELECT comicvine_id
		FROM volumes
		WHERE id = ?;
		""",
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
			comicvine_id = ?
	""", volume_data['issues'])

	return

#=====================
# Library class
#=====================
class Library:
	sorting_orders = {
		'title': 'title, year, volume_number',
		'year': 'year, title, volume_number',
		'volume_number': 'volume_number, title, year'
	}
	
	def __format_lib_output(self, library: List[dict]) -> List[dict]:
		for i, v in enumerate(library):
			data = dict(v)
			data.update({
				'monitored': v['monitored'] == 1,
				'cover': f'/api/volumes/{v["id"]}/cover'
			})
			library[i] = data
		return library
	
	def get_volumes(self, sort: str='title') -> List[dict]:
		#determine sorting order
		sort = self.sorting_orders[sort]

		#fetch all volumes
		volumes = get_db('dict').execute(f"""
			SELECT
				id, comicvine_id,
				title, year, publisher,
				volume_number, description,
				monitored
			FROM volumes
			ORDER BY {sort};
		""").fetchall()

		volumes = self.__format_lib_output(volumes)
		
		return volumes
		
	def search(self, query: str) -> List[dict]:
		volumes = get_db('dict').execute("""
			SELECT
				id, comicvine_id,
				title, year, publisher,
				volume_number, description,
				monitored
			FROM volumes
			WHERE LOWER(title) = ?
				OR LOWER(title) LIKE '%' || ? || '%'
			ORDER BY title, year, volume_number;
			""",
			[query.lower()] * 2
		).fetchall()
		
		volumes = self.__format_lib_output(volumes)
		
		return volumes

	def get_volume(self, volume_id: int) -> Volume:
		volume_found = get_db().execute(
			"SELECT 1 FROM volumes WHERE id = ? LIMIT 1",
			(volume_id,)
		).fetchone()

		if volume_found:
			return Volume(volume_id)
		raise VolumeNotFound

	def get_issue(self, issue_id: int) -> Issue:
		issue_found = get_db().execute(
			"SELECT id FROM issues WHERE id = ? LIMIT 1",
			(issue_id,)
		).fetchone()
		if issue_found:
			return Issue(issue_id)
		raise IssueNotFound

	def add(self, comicvine_id: str, root_folder_id: int, monitor: bool=True) -> int:
		cursor = get_db()

		# Check if volume isn't already added
		already_exists = cursor.execute(
			"SELECT id FROM volumes WHERE comicvine_id = ? LIMIT 1",
			(comicvine_id,)
		).fetchone()
		if already_exists:
			raise VolumeAlreadyAdded

		# Check if root folder exists
		# Raises RootFolderNotFound when id is invalid
		root_folder = RootFolders().get_one(root_folder_id, use_cache=False)['folder']

		# Get volume info
		volume_data = ComicVine().fetch_volume(comicvine_id)
		volume_data.update({
			'monitored': monitor,
			'root_folder': root_folder_id,
		})

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
	return ComicVine().search_volumes(query)
