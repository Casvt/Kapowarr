#-*- coding: utf-8 -*-

"""
Handling folders, files and filenames.
"""

import logging
from os import listdir, makedirs, remove, scandir, sep, stat
from os.path import (abspath, basename, commonpath, dirname, exists, isdir,
                     isfile, join, relpath, samefile, splitext)
from shutil import copytree, move, rmtree
from typing import Iterable, List, Tuple, Union

from backend.db import get_db


def folder_path(*folders: str) -> str:
	"""Turn filepaths relative to the project folder into absolute paths.

	Returns:
		str: The absolute filepath.
	"""
	return join(dirname(dirname(abspath(__file__))), *folders)


def folder_is_inside_folder(
	base_folder: str,
	folder: str
) -> bool:
	"""Check if folder is inside base_folder.

	Args:
		base_folder (str): The base folder to check against.
		folder (str): The folder that should be inside base_folder.

	Returns:
		bool: Whether or not folder is in base_folder.
	"""
	return (abspath(folder) + sep).startswith(abspath(base_folder) + sep)


def find_lowest_common_folder(files: List[str]) -> str:
	"""Find the lowest folder that is shared between the files

	Args:
		files (List[str]): The list of files to find the lowest common folder for

	Returns:
		str: The path of the lowest common folder
	"""
	if len(files) == 1:
		return dirname(files[0])

	return commonpath(files)


def delete_file_folder(path: str) -> None:
	"""Delete a file or folder. In the case of a folder, it is deleted recursively.

	Args:
		path (str): The path to the file or folder.
	"""
	if isfile(path):
		remove(path)
	elif isdir(path):
		rmtree(path, ignore_errors=True)
	return


def list_files(folder: str, ext: Iterable[str] = []) -> List[str]:
	"""List all files in a folder recursively with absolute paths

	Args:
		folder (str): The root folder to search through

		ext (Iterable[str], optional): File extensions to only include.
			Give WITH preceding `.`.

			Defaults to [].

	Returns:
		List[str]: The paths of the files in the folder
	"""
	files: List[str] = []
	for f in scandir(folder):
		if f.is_dir():
			files += list_files(f.path, ext)

		elif f.is_file():
			if (not f.name.startswith('.')
			and (
				not ext
				or splitext(f.name)[1].lower() in ext
			)):
				files.append(f.path)

	return files


def propose_basefolder_change(
	files: Iterable[str],
	current_base_folder: str,
	desired_base_folder: str
) -> List[Tuple[str, str]]:
	"""Propose new filenames with a different base folder for a list of files.
	E.g. /current/base/folder/file.ext -> /desired_base_folder/file.ext

	Args:
		files (List[str]): List of files to change base folder for.
		current_base_folder (str): Current base folder, to replace.
		desired_base_folder (str): Desired base folder, to replace with.

	Returns:
		List[Tuple[str, str]]: First entry of sub-tuple is old filename,
		second is new filename.
	"""
	file_changes = [
		(
			f,
			join(
				desired_base_folder,
				relpath(
					f,
					current_base_folder
				)
			)
		)
		for f in files
	]
	return file_changes


def delete_empty_folders(top_folder: str, root_folder: str) -> None:
	"""Keep deleting empty folders until we reach a folder with content
	or the root folder

	Args:
		top_folder (str): The folder to start deleting from
		root_folder (str): The root folder to stop at in case we reach it
	"""
	logging.debug(f'Deleting folders from {top_folder} until {root_folder}')

	if not folder_is_inside_folder(root_folder, top_folder):
		logging.error(f'The folder {top_folder} is not in {root_folder}')
		return

	parent_folder = top_folder
	child_folder = None

	while parent_folder:
		if exists(parent_folder):
			if samefile(parent_folder, root_folder):
				break

			if listdir(parent_folder) not in ([], [child_folder]):
				# Folder has content and it's not only the empty child
				break

		child_folder = basename(parent_folder)
		parent_folder = dirname(parent_folder)

	if child_folder:
		lowest_empty_folder = join(parent_folder, child_folder)
		logging.debug(f'Deleting folder and children: {lowest_empty_folder}')
		delete_file_folder(lowest_empty_folder)

	return


def create_folder(folder: str) -> None:
	"""Create a folder

	Args:
		folder (str): The path to the folder to create.
	"""
	makedirs(folder, exist_ok=True)
	return


def create_volume_folder(
	root_folder: str,
	volume_id: int,
	volume_folder: Union[str, None] = None
) -> str:
	"""Generate, register and create a folder for a volume.

	Args:
		root_folder (str): The rootfolder (path, not id).
		volume_id (int): The id of the volume for which the folder is.
		volume_folder (Union[str, None], optional): Custom volume folder.
			Defaults to None.

	Returns:
		str: The path to the folder.
	"""
	# Generate and register folder
	if volume_folder is None:
		from backend.naming import generate_volume_folder_name

		volume_folder = join(
			root_folder, generate_volume_folder_name(volume_id)
		)
	else:
		from backend.naming import make_filename_safe
		volume_folder = join(
			root_folder, make_filename_safe(volume_folder)
		)
	get_db().execute(
		"UPDATE volumes SET folder = ? WHERE id = ?",
		(volume_folder, volume_id)
	)

	create_folder(volume_folder)

	return volume_folder


def rename_file(before: str, after: str) -> None:
	"""Rename a file, taking care of new folder locations and
	the possible complications with files on OS'es.

	Args:
		before (str): The current filepath of the file.
		after (str): The new desired filepath of the file.
	"""
	if folder_is_inside_folder(before, after):
		# Cannot move folder into itself
		return

	logging.debug(f'Renaming file {before} to {after}')

	create_folder(dirname(after))

	# Move file into folder
	try:
		move(before, after)
	except PermissionError:
		# Happens when moving between an NFS file system.
		# Raised when chmod is used inside.
		# Checking the source code, chmod is used at the very end,
		# 	so just skipping it is alright I think.
		pass

	return


def copy_directory(source: str, target: str) -> None:
	"""Copy a directory.

	Args:
		source (str): The path to the source directory.
		target (str): The path to where the directory should be copied.
	"""
	try:
		copytree(source, target)
	except PermissionError:
		# Happens when moving between an NFS file system.
		# Raised when chmod is used inside.
		# Checking the source code, chmod is used at the very end,
		# 	so just skipping it is alright I think.
		pass

	return


def get_file_id(
	filepath: str,
	add_file: bool
) -> int:
	"""Get the ID of a file, and add it first if requested.

	Args:
		filepath (str): The file to get the ID of.
		add_file (bool): Add file to database first before getting ID.

	Returns:
		int: The id of the entry in the database
	"""
	cursor = get_db()

	if add_file:
		logging.debug(f'Adding file to the database: {filepath}')
		cursor.execute(
			"INSERT OR IGNORE INTO files(filepath, size) VALUES (?,?)",
			(filepath, stat(filepath).st_size)
		)

	file_id = cursor.execute(
		"SELECT id FROM files WHERE filepath = ? LIMIT 1",
		(filepath,)
	).fetchone()[0]

	return file_id


def filepath_to_volume_id(filepath: str) -> int:
	"""Get the ID of the volume based on a filename.

	Args:
		filepath (str): The filepath based on which to get the volume ID.

	Returns:
		int: The ID of the volume.
	"""
	volume_id: int = get_db().execute("""
		SELECT i.volume_id
		FROM
			files f
			INNER JOIN issues_files if
			INNER JOIN issues i
		ON
			f.id = if.file_id
			AND if.issue_id = i.id
		WHERE f.filepath = ?
		LIMIT 1;
		""",
		(filepath,)
	).fetchone()[0]

	return volume_id
