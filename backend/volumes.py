#-*- coding: utf-8 -*-

import logging
from asyncio import run
from dataclasses import dataclass
from io import BytesIO
from os import remove
from os.path import abspath, isdir, join, relpath
from re import IGNORECASE, compile
from time import time
from typing import Any, Dict, List, Tuple, Union

from backend.comicvine import ComicVine
from backend.custom_exceptions import (IssueNotFound, TaskForVolumeRunning, VolumeAlreadyAdded,
                                       VolumeDownloadedFor, VolumeNotFound)
from backend.db import get_db
from backend.enums import SpecialVersion
from backend.file_extraction import extract_filename_data, supported_extensions
from backend.files import (create_volume_folder, delete_empty_folders,
                           folder_is_inside_folder, get_file_id, list_files,
                           propose_basefolder_change, rename_file)
from backend.helpers import first_of_column, reversed_tuples
from backend.matching import file_importing_filter
from backend.root_folders import RootFolders

os_regex = compile(r'(?<!>)\bone[\- ]?shot\b(?!<)', IGNORECASE)
hc_regex = compile(r'(?<!>)\bhard[\- ]?cover\b(?!<)', IGNORECASE)
vol_regex = compile(r'^volume\.?\s\d+$', IGNORECASE)
def determine_special_version(
	volume_title: str,
	volume_description: str,
	issue_titles: List[str]
) -> SpecialVersion:
	"""Determine if a volume is a special version.

	Args:
		volume_title (str): The title of the volume.
		volume_description (str): The description of the volume.
		issue_titles (List[str]): The titles of all issues in the volume.

	Returns:
		SpecialVersion: The result.
	"""
	if os_regex.search(volume_title):
		return SpecialVersion.ONE_SHOT

	if issue_titles:
		if (issue_titles[0] or '').lower() == 'hc':
			return SpecialVersion.HARD_COVER

		if all(
			vol_regex.search(title or '')
			for title in issue_titles
		):
			return SpecialVersion.VOLUME_AS_ISSUE

	if volume_description and len(volume_description.split('. ')) == 1:
		# Description is only one sentence, so it's allowed to
		# look in description for special version.
		# Only one sentence is allowed because otherwise the description
		# could be referencing a special version that isn't this one,
		# leading to a false hit.
		if os_regex.search(volume_description):
			return SpecialVersion.ONE_SHOT
		
		if hc_regex.search(volume_description):
			return SpecialVersion.HARD_COVER

	if len(issue_titles) == 1:
		return SpecialVersion.TPB

	return SpecialVersion.NORMAL

#=====================
# Main issue class
#=====================
class Issue:
	def __init__(
		self,
		id: int,
		check_existence: bool = False
	) -> None:
		"""Create instance of issue.

		Args:
			id (int): The ID of the issue.
			check_existence (bool, optional): Check if issue exists based on ID.
				Defaults to False.

		Raises:
			IssueNotFound: The issue was not found.
				Can only be raised when check_existence is `True`.
		"""		
		self.id = id
		
		if check_existence:
			if not (1,) in get_db().execute(
				"SELECT 1 FROM issues WHERE id = ? LIMIT 1;",
				(self.id,)
			):
				raise IssueNotFound

	@classmethod
	def from_volume_and_calc_number(
		cls,
		volume_id: int,
		calculated_issue_number: float
	) -> None:
		"""Create instance of issue based on volume ID and calculated issue
		number of issue.

		Args:
			volume_id (int): The ID of the volume that the issue is in.
			calculated_issue_number (float): The calculated issue number of
			the issue.

		Raises:
			IssueNotFound: No issue found with the given arguments.
		"""
		issue_id = get_db().execute("""
			SELECT id
			FROM issues
			WHERE volume_id = ?
				AND calculated_issue_number = ?
			LIMIT 1;
			""",
			(volume_id, calculated_issue_number)
		).fetchone()
		
		if not issue_id:
			raise IssueNotFound
		
		return cls(issue_id[0])

	def get_public_keys(self) -> dict:
		"""Get data about the issue for the public to see (the API).

		Returns:
			dict: The data.
		"""
		cursor = get_db(dict)
		
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
		data['files'] = self.get_files()
		return data

	def get_keys(self, keys: Union[Tuple[str], str]) -> dict:
		"""Get a dict with the values of the given keys.

		Args:
			keys (Union[Tuple[str], str]): The keys or just one key.

		Returns:
			dict: The dict with the keys and their values.
		"""
		if isinstance(keys, str):
			keys = (keys,)

		result = dict(
			get_db(dict).execute(
				f"SELECT {','.join(keys)} FROM issues WHERE id = ? LIMIT 1;",
				(self.id,)
			).fetchone()
		)

		return result

	def __getitem__(self, key: str) -> Any:
		value = get_db().execute(
			f"SELECT {key} FROM issues WHERE id = ? LIMIT 1;",
			(self.id,)
		).fetchone()[0]
		return value

	def get_files(self) -> List[str]:
		"""Get all files linked to the issue.

		Returns:
			List[str]: List of the files.
		"""
		files = first_of_column(get_db().execute(f"""
			SELECT DISTINCT filepath
			FROM files f
			INNER JOIN issues_files if
			ON f.id = if.file_id
			WHERE if.issue_id = ?
			ORDER BY filepath;
			""",
			(self.id,)
		))
		return files

	def __setitem__(self, key: str, value: Any) -> None:
		if key != 'monitored':
			raise KeyError

		logging.debug(f'For issue {self.id}, setting {key} to {value}')

		get_db().execute(
			f"UPDATE issues SET {key} = ? WHERE id = ?;",
			(value, self.id)
		)

		return

def get_calc_number_range(
	volume_id: int,
	calculated_issue_number_start: float,
	calculated_issue_number_end: float
) -> List[float]:
	"""Get all calculated issue numbers between a range for a volume.

	Args:
		volume_id (int): The ID of the volume.
		calculated_issue_number_start (float): Start of the range.
		calculated_issue_number_end (float): End of the range.

	Returns:
		List[float]: All calculated issue numbers in the range.
	"""
	result = first_of_column(get_db().execute("""
		SELECT calculated_issue_number
		FROM issues
		WHERE
			volume_id = ?
			AND ? <= calculated_issue_number
			AND calculated_issue_number <= ?;
		""",
		(
			volume_id,
			calculated_issue_number_start,
			calculated_issue_number_end
		)
	))
	return result

def get_calc_number_id_range(
	volume_id: int,
	calculated_issue_number_start: float,
	calculated_issue_number_end: float
) -> List[int]:
	"""Get all id's of issues between a range for a volume.

	Args:
		volume_id (int): The ID of the volume.
		calculated_issue_number_start (float): Start of the range.
		calculated_issue_number_end (float): End of the range.

	Returns:
		List[int]: All issue id's in the range.
	"""
	result = first_of_column(get_db().execute("""
		SELECT id
		FROM issues
		WHERE
			volume_id = ?
			AND ? <= calculated_issue_number
			AND calculated_issue_number <= ?;
		""",
		(
			volume_id,
			calculated_issue_number_start,
			calculated_issue_number_end
		)
	))
	return result

#=====================
# Main volume class
#=====================
@dataclass(frozen=True)
class VolumeData:
	# All types should actually be Union[None, {TYPE}]
	id: int = None
	comicvine_id: int = None
	title: str = None
	year: int = None
	publisher: str = None
	volume_number: int = None
	description: str = None
	monitored: bool = None
	root_folder: int = None
	folder: str = None
	special_version: SpecialVersion = None


class _VolumeBackend:
	def _check_existence(self) -> bool:
		"""Check if volume exists based on ID

		Returns:
			bool: Whether the volume exists or not
		"""
		volume_found = get_db().execute(
			"SELECT 1 FROM volumes WHERE id = ? LIMIT 1;",
			(self.id,)
		)
		
		return (1,) in volume_found
	
	def _get_keys(self, keys: Union[Tuple[str], str]) -> dict:
		"""Get a dict with the values of the given keys.

		Args:
			keys (Union[Tuple[str], str]): The keys or just one key.

		Returns:
			dict: The dict with the keys and their values.
		"""
		if isinstance(keys, str):
			keys = (keys,)
		
		result = dict(
			get_db(dict).execute(
				f"SELECT {','.join(keys)} FROM volumes WHERE id = ? LIMIT 1;",
				(self.id,)
			).fetchone()
		)
		
		if 'special_version' in result:
			result['special_version'] = SpecialVersion(result['special_version'])

		return result

	def _get_cover(self) -> BytesIO:
		"""Get the cover of the volume.

		Returns:
			BytesIO: The cover.
		"""
		cover = get_db().execute(
			"SELECT cover FROM volumes WHERE id = ? LIMIT 1",
			(self.id,)
		).fetchone()[0]
		return BytesIO(cover)

	def _get_last_issue_date(self) -> Union[str, None]:
		"""Get the date of the last issue that has a release date.

		Returns:
			Union[str, None]: The release date of the last issue with one.
			`None` if there is no issue or no issue with a release date.
		"""
		last_issue_date = get_db().execute("""
			SELECT MAX(date) AS last_issue_date
			FROM issues
			WHERE volume_id = ?;
			""",
			(self.id,)
		).fetchone()[0]
		
		return last_issue_date

	def _check_key(self, key: str) -> bool:
		"""Check key is allowed.

		Args:
			key (str): The key to check.

		Returns:
			bool: Whether it's allowed or not.
		"""
		return key in (
			*VolumeData.__annotations__,
			'cover',
			'custom_folder',
			'last_cv_fetch',
			'volume_folder'
		)

	def _set_value(self, key: str, value: Any) -> None:
		"""Set the value of the key.

		Args:
			key (str): The key to set the value for.
			value (Any): The value to set.
		"""
		if key == 'special_version' and isinstance(value, SpecialVersion):
			value = value.value

		logging.debug(f'For volume {self.id}, setting {key} to {value}')

		get_db().execute(
			f"UPDATE volumes SET {key} = ? WHERE id = ?;",
			(value, self.id)
		)
		return

	def _change_root_folder(self, root_folder_id: int) -> None:
		"""Change the root folder of the volume.

		Args:
			root_folder_id (int): The root folder ID of the new root folder.
		"""
		cursor = get_db()
		root_folders = cursor.execute("""
			SELECT DISTINCT
				rf.id, rf.folder
			FROM root_folders rf
			LEFT JOIN volumes v
			ON rf.id = v.root_folder
			WHERE v.id = ? OR rf.id = ?
			LIMIT 2;
			""",
			(self.id, root_folder_id)
		).fetchall()

		if len(root_folders) != 2:
			return

		volume_folder = self['folder']

		current_index = int(
			not folder_is_inside_folder(root_folders[0][1], volume_folder)
		)
		current_root_folder = root_folders[current_index]
		desired_root_folder = root_folders[current_index - 1]		

		logging.info(f'Changing root folder of volume {self.id} from {current_root_folder[1]} to {desired_root_folder[1]}')

		file_changes = propose_basefolder_change(
			self.get_files(),
			current_root_folder[1],
			desired_root_folder[1]
		)
		for old_name, new_name in file_changes:
			rename_file(
				old_name,
				new_name
			)
		cursor.executemany(
			"UPDATE files SET filepath = ? WHERE filepath = ?",
			reversed_tuples(file_changes)
		)
		
		self._set_value('root_folder', desired_root_folder[0])
		self['folder'] = propose_basefolder_change(
			(volume_folder,),
			current_root_folder[1],
			desired_root_folder[1]
		)[0][1]
		
		delete_empty_folders(
			volume_folder,
			current_root_folder[1]
		)

		return

	def _change_volume_folder(
		self,
		new_volume_folder: Union[str, None]
	) -> None:
		"""Change the volume folder of the volume.

		Args:
			new_volume_folder (Union[str, None]): The new folder,
			or `None` if the default folder should be generated and used.
		"""
		from backend.naming import generate_volume_folder_name, make_filename_safe
		current_volume_folder = self['folder']
		root_folder = RootFolders()[self['root_folder']]

		if new_volume_folder is None or new_volume_folder == '':
			# Generate default folder and set custom_folder to False
			new_volume_folder = generate_volume_folder_name(self.id)
			custom_folder = False
		
		else:
			# Make custom folder safe and set custom_folder to True
			new_volume_folder = make_filename_safe(new_volume_folder)
			custom_folder = True

		new_volume_folder = abspath(join(root_folder, new_volume_folder))
		
		if current_volume_folder == new_volume_folder:
			return

		logging.info(f'Moving volume folder from {current_volume_folder} to {new_volume_folder}')

		self['custom_folder'] = custom_folder		
		self['folder'] = new_volume_folder
		
		file_changes = propose_basefolder_change(
			self.get_files(),
			current_volume_folder,
			new_volume_folder
		)
		for old_name, new_name in file_changes:
			rename_file(
				old_name,
				new_name
			)
		get_db().executemany(
			"UPDATE files SET filepath = ? WHERE filepath = ?",
			reversed_tuples(file_changes)
		)

		if folder_is_inside_folder(new_volume_folder, current_volume_folder):
			# New folder is parent of current folder, so delete up to new folder.
			delete_empty_folders(
				current_volume_folder,
				new_volume_folder
			)
		else:
			delete_empty_folders(
				current_volume_folder,
				root_folder
			)

		return


class Volume(_VolumeBackend):
	def __init__(
		self,
		id: int,
		check_existence: bool = False
	) -> None:
		"""Create instance of Volume.

		Args:
			id (int): The ID of the volume.
			check_existence (bool, optional): Check if volume exists, based on ID.
				Defaults to False.

		Raises:
			VolumeNotFound: The volume was not found.
				Can only be raised when check_existence is `True`.
		"""
		self.id = id

		if check_existence and not self._check_existence():
			raise VolumeNotFound

		return

	def get_public_keys(self) -> dict:
		"""Get data about the volume for the public to see (the API).

		Returns:
			dict: The data.
		"""
		cursor = get_db(dict)

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
				) AS issues_downloaded,
				(
					SELECT SUM(size) FROM (
						SELECT DISTINCT f.id, size
						FROM issues i
						INNER JOIN issues_files if
						INNER JOIN files f
						ON i.id = if.issue_id
							AND if.file_id = f.id
						WHERE volume_id = v.id
					)
				) AS total_size
			FROM volumes v
			INNER JOIN root_folders rf
			ON v.root_folder = rf.id
			WHERE v.id = ?
			LIMIT 1;
			""",
			(self.id,)
		)
		volume_info = dict(cursor.fetchone())
		volume_info['volume_folder'] = relpath(
			volume_info['folder'],
			volume_info['root_folder_path']
		)
		del volume_info['root_folder_path']
		volume_info['issues'] = self.get_issues()

		return volume_info

	def __getitem__(self, key: str) -> Any:
		if key == 'cover':
			return self._get_cover()
	
		if key == 'last_issue_date':
			return self._get_last_issue_date()

		return self._get_keys(key)[key]

	def get_keys(self, keys: Tuple[str]) -> VolumeData:
		"""The data of the volume based on the keys.

		Args:
			keys (Tuple[str]): The keys of which to get the value.

		Returns:
			VolumeData: The data. The given keys will have their values set.
				The other keys will have `None` set as their value.
		"""
		data = self._get_keys(keys)
		result = VolumeData(**data)
		return result

	def get_files(self, issue_id: int = None) -> List[str]:
		"""Get the files matched to the volume.

		Args:
			issue_id (int, optional): The specific issue to get the files of.
				Based on ID of issue.

				Defaults to None.

		Returns:
			List[str]: List of filepaths.
		"""
		if not issue_id:
			files = first_of_column(get_db().execute(f"""
				SELECT DISTINCT filepath
				FROM files f
				INNER JOIN issues_files if
				INNER JOIN issues i
				ON
					f.id = if.file_id
					AND if.issue_id = i.id
				WHERE volume_id = ?;
				""",
				(self.id,)
			))

		else:
			files = first_of_column(get_db().execute(f"""
				SELECT DISTINCT filepath
				FROM files f
				INNER JOIN issues_files if
				ON f.id = if.file_id
				WHERE if.issue_id = ?;
				""",
				(issue_id,)
			))
			
		return files

	def get_issues(self) -> List[dict]:
		"""Get list of issues that are in the volume.

		Returns:
			List[dict]: The list of issues.
		"""
		issues = [
			dict(i) for i in get_db(dict).execute("""
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
			issue['files'] = self.get_files(issue['id'])
		
		return issues

	def __setitem__(self, key: str, value: Any) -> None:
		if not self._check_key(key):
			raise KeyError
		
		if key == 'root_folder':
			self._change_root_folder(value)
		
		elif key == 'volume_folder':
			self._change_volume_folder(value)

		else:
			self._set_value(key, value)

		return

	def update(self, changes: dict) -> None:
		"""Change settings of the volume.

		Args:
			changes (dict): The keys with new values.

		Raises:
			KeyError: Key is unknown or not allowed.
		"""		
		if any(not self._check_key(k) for k in changes):
			raise KeyError

		for key, value in changes.items():
			self[key] = value

	def delete(self, delete_folder: bool = False) -> None:
		"""Delete the volume from the library

		Args:
			delete_folder (bool, optional): Also delete the volume folder and
			it's contents.
				Defaults to False.

		Raises:
			VolumeDownloadedFor: There is a download in the queue for the volume.
		"""
		from backend.tasks import TaskHandler
		
		logging.info(f'Deleting volume {self.id} with delete_folder set to {delete_folder}')
		cursor = get_db()

		# Check if there is no task running for the volume
		if TaskHandler.task_for_volume_running(self.id):
			raise TaskForVolumeRunning(self.id)

		# Check if nothing is downloading for the volume
		downloading_for_volume = cursor.execute("""
			SELECT 1
			FROM download_queue
			WHERE volume_id = ?
			LIMIT 1;
			""",
			(self.id,)
		).fetchone()
		if downloading_for_volume:
			raise VolumeDownloadedFor(self.id)

		if delete_folder:
			for f in self.get_files():
				remove(f)
			
			delete_empty_folders(
				self['folder'],
				RootFolders()[self['root_folder']]
			)

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

	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}; ID {self.id}>'


def scan_files(volume_id: int) -> None:
	"""Scan inside the volume folder for files and map them to issues

	Args:
		volume_id (int): The ID of the volume to scan for.
	"""
	logging.debug(f'Scanning for files for {volume_id}')
	cursor = get_db()
	
	volume = Volume(volume_id, check_existence=False)
	volume_data = volume.get_keys(
		('folder', 'root_folder', 'special_version', 'year', 'id')
	)
	volume_issues = volume.get_issues()
	# We're going to check a lot of a string is in here,
	# so convert to set for speed improvement.
	volume_files = set(volume.get_files())

	if not isdir(volume_data.folder):
		root_folder = RootFolders()[volume_data.root_folder]
		create_volume_folder(root_folder, volume_id)

	bindings = []
	folder_contents = list_files(
		folder=volume_data.folder,
		ext=supported_extensions
	)
	for file in folder_contents:
		file_data = extract_filename_data(file)

		# Check if file matches volume
		if not file_importing_filter(file_data, volume_data, volume_issues):
			continue

		if (
			volume_data.special_version not in (
				SpecialVersion.VOLUME_AS_ISSUE,
				SpecialVersion.NORMAL
			)
			and file_data['special_version']
		):
			file_id = get_file_id(
				file,
				add_file = not file in volume_files
			)

			bindings.append((file_id, volume_issues[0]['id']))

		# Search for issue number(s)
		if (file_data['issue_number'] is not None
		or volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE):

			if volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE:
				if file_data['issue_number'] is not None:
					issue_range = file_data['issue_number']
				else:
					issue_range = file_data['volume_number']
			else:
				issue_range = file_data['issue_number']

			if not isinstance(issue_range, tuple):
				issue_range = (issue_range, issue_range)

			matching_issues = get_calc_number_id_range(
				volume_id,
				*issue_range
			)

			if matching_issues:
				file_id = get_file_id(
					file,
					add_file = not file in volume_files
				)

				for issue_id in matching_issues:
					bindings.append((file_id, issue_id))

	# Get current bindings
	current_bindings = cursor.execute("""
		SELECT if.file_id, if.issue_id
		FROM issues_files if
		INNER JOIN issues i
		ON if.issue_id = i.id
		WHERE i.volume_id = ?;
		""",
		(volume_id,)
	).fetchall()

	# Delete bindings that aren't in new bindings
	delete_bindings = (b for b in current_bindings if b not in bindings)
	cursor.executemany(
		"DELETE FROM issues_files WHERE file_id = ? AND issue_id = ?;",
		delete_bindings
	)

	# Add bindings that aren't in current bindings
	new_bindings = (b for b in bindings if b not in current_bindings)
	cursor.executemany(
		"INSERT INTO issues_files(file_id, issue_id) VALUES (?, ?);",
		new_bindings
	)

	# Delete all file entries that aren't binded
	# AKA files that were present last scan but this scan not anymore
	cursor.execute("""
		DELETE FROM files
		WHERE rowid IN (
			SELECT f.rowid
			FROM files f
			LEFT JOIN issues_files if
			ON f.id = if.file_id
			WHERE if.file_id IS NULL
		);
	""")

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
	volume_datas = run(cv.fetch_volumes_async(str_ids))
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
	issue_datas = run(cv.fetch_issues_async([str(v['comicvine_id']) for v in volume_datas]))
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
		""",
		issue_updates
	)
	cursor.connection.commit()
	
	# Check special version
	sv_updates = list((
			determine_special_version(
				volume_data['title'],
				volume_data['description'],
				first_of_column(cursor.execute(
					"SELECT title FROM issues WHERE volume_id = ?;",
					(ids[volume_data['comicvine_id']],)
				))
			).value,
			ids[volume_data['comicvine_id']]
		)
		for volume_data in volume_datas
	)
	
	cursor.executemany("""
		UPDATE volumes
		SET special_version = ?
		WHERE id = ?;
		""",
		sv_updates
	)

	# Scan for files
	if volume_id:
		scan_files(volume_id)
	else:
		cursor2 = get_db(temp=True)
		cursor2.execute("SELECT id FROM volumes;")
		for volume in cursor2:
			scan_files(volume[0])
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
	
	filters = {
		'wanted': 'WHERE issues_downloaded_monitored < issue_count_monitored',
		'monitored': 'WHERE monitored = 1'
	}

	def get_volumes(self,
		sort: str='title',
		filter: Union[str, None] = None
	) -> List[dict]:
		"""Get all volumes in the library

		Args:
			sort (str, optional): How to sort the list.
			`title`, `year`, `volume_number`, `recently_added` and `publisher` allowed.
				Defaults to 'title'.

			filter (Union[str, None], optional): Apply a filter to the list.
			`wanted` and `monitored` allowed.
				Defaults to None.

		Returns:
			List[dict]: The list of volumes in the library.
		"""		
		sort = self.sorting_orders[sort]
		filter = self.filters.get(filter, '')

		volumes = [
			dict(v) for v in get_db(dict).execute(f"""
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
				{filter}
				ORDER BY {sort};
				"""
			)
		]

		return volumes
		
	def search(self,
		query: str,
		sort: str='title',
		filter: Union[str, None] = None
	) -> List[dict]:
		"""Search in the library with a query

		Args:
			query (str): The query to search with
			sort (str, optional): How to sort the list.
			`title`, `year`, `volume_number`, `recently_added` and `publisher` allowed.
				Defaults to 'title'.

			filter (Union[str, None], optional): Apply a filter to the list.
			`wanted` and `monitored` allowed.
				Defaults to None.

		Returns:
			List[dict]: The resulting list of matching volumes in the library
		"""
		volumes = [
			v
			for v in self.get_volumes(sort, filter)
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
		return Volume(volume_id, check_existence=True)

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
		return Issue(issue_id, check_existence=True)
		
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
		root_folder = RootFolders()[root_folder_id]

		volume_data = run(ComicVine().fetch_volume_async(comicvine_id))
		volume_data['monitored'] = monitor
		volume_data['root_folder'] = root_folder_id
		
		special_version = determine_special_version(
			volume_data['title'],
			volume_data['description'],
			tuple(i['title'] for i in volume_data['issues'])
		).value

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
		cursor = get_db(dict)
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
