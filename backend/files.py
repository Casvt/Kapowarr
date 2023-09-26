#-*- coding: utf-8 -*-

"""This file contains function regarding files and integrating them into Kapowarr

extract_filename_data is inspired by the file parsing of Kavita and Comictagger:
	https://github.com/Kareadita/Kavita/blob/develop/API/Services/Tasks/Scanner/Parser/Parser.cs
	https://github.com/comictagger/comictagger/blob/develop/comicapi/filenameparser.py
"""

import logging
from os import listdir, makedirs, remove, scandir, sep, stat
from os.path import (abspath, basename, dirname, exists, isdir, join, relpath,
                     samefile, splitext)
from re import IGNORECASE, compile
from shutil import move, rmtree
from typing import List, Tuple, Union
from urllib.parse import unquote

from backend.db import get_db
from backend.root_folders import RootFolders

alphabet = 'abcdefghijklmnopqrstuvwxyz'
alphabet = {letter: str(alphabet.index(letter) + 1).zfill(2) for letter in alphabet}
digits = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
image_extensions = ('.png','.jpeg','.jpg','.webp','.gif')
supported_extensions = image_extensions + ('.cbz','.zip','.rar','.cbr','.tar.gz','.7zip','.7z','.cb7','.cbt','.epub','.pdf')
file_extensions = r'\.(' + '|'.join(e[1:] for e in supported_extensions) + r')$'
volume_regex_snippet = r'\b(?:v(?:ol|olume)?)(?:\.\s|[\.\-\s])?(\d+|I{1,3})\b'
year_regex_snippet = r'(?:(\d{4})(?:-\d{2}){0,2}|(\d{4})[\s\.]?-[\s\.]?\d{4}|(?:\d{2}-){1,2}(\d{4})|(\d{4})[\s\.\-]Edition|(\d{4})-\d{4}\s{3}\d{4})'
issue_regex_snippet = r'(?!\d+(?:th|rd|st))(?<!’)\d+(?:\.\d{1,2}|\w{1,2}|[\s\-\.]?½)?'

# Cleaning the filename
strip_filename_regex = compile(r'\(.*?\)|\[.*?\]|\{.*?\}', IGNORECASE)
strip_filename_regex_2 = compile(file_extensions, IGNORECASE)

# Supporting languages by translating them
russian_volume_regex = compile(r'Томa?[\s\.]?(\d+)', IGNORECASE)
russian_volume_regex_2 = compile(r'(\d+)[\s\.]?Томa?', IGNORECASE)
chinese_volume_regex = compile(r'第(\d+)(?:卷|册)', IGNORECASE)
chinese_volume_regex_2 = compile(r'(?:卷|册)(\d+)', IGNORECASE)
korean_volume_regex = compile(r'제?(\d+)권', IGNORECASE)
japanese_volume_regex = compile(r'(\d+)巻', IGNORECASE)

# Extract data from (stripped)filename
special_version_regex = compile(r'(?:\b|\()(tpb|os|one[\- ]?shot|ogn|gn|hard[\- ]?cover|cover)(?:\b|\))', IGNORECASE)
volume_regex = compile(volume_regex_snippet, IGNORECASE)
volume_folder_regex = compile(volume_regex_snippet + r'|^(\d+)$', IGNORECASE)
issue_regex = compile(r'\( (-?' + issue_regex_snippet + r')\)', IGNORECASE)
issue_regex_2 = compile(r'(?<!\()\b(?:c(?:hapter)?|issue|page)s?(?:[\s\-\.]?|\s\-\s)#?(\-?' + issue_regex_snippet + r'(?:[\s\.]?\-[\s\.]?\-?' + issue_regex_snippet + r')?)\b(?!\))', IGNORECASE)
issue_regex_3 = compile(r'(' + issue_regex_snippet + r')[\s\-\.]?\(?[\s\-\.]?of[\s\-\.]?' + issue_regex_snippet + r'\)?', IGNORECASE)
issue_regex_4 = compile(r'(?<!--)#?(' + issue_regex_snippet + r'[\s\.]?-[\s\.]?' + issue_regex_snippet + r')\b(?!--)', IGNORECASE)
issue_regex_5 = compile(r'#(\-?' + issue_regex_snippet + r')\b(?![\s\.]?\-[\s\.]?' + issue_regex_snippet + r')', IGNORECASE)
issue_regex_6 = compile(r'(?<!\()\b(' + issue_regex_snippet + r')\b(?!\))', IGNORECASE)
issue_regex_7 = compile(r'^(-?' + issue_regex_snippet + r')$', IGNORECASE)
year_regex = compile(r'\(' + year_regex_snippet + r'\)|--' + year_regex_snippet + r'--|, ' + year_regex_snippet + r'\s{3}|\b(?:(?:\d{2}-){1,2}(\d{4})|(\d{4})(?:-\d{2}){1,2})\b', IGNORECASE)
series_regex = compile(r'(^(\d+\.)?\s+|\s(?=\s)|[\s,]+$)')
annual_regex = compile(r'\+[\s\.]?annuals?|annuals?[\s\.]?\+|^((?!annuals?).)*$', IGNORECASE)

def _calc_float_issue_number(issue_number: str) -> Union[float, None]:
	"""Convert an issue number from string to representive float

	Args:
		issue_number (str): The issue number to convert

	Returns:
		Union[float, None]: Either the float version or `None` if it failed to convert
	"""
	try:
		# Targets numbers that are already valid float numbers, just in string form
		return float(issue_number)
	except ValueError:
		pass

	# Issue has special number notation
	issue_number = issue_number.replace(',','.').rstrip('.').lower()
	if issue_number.startswith('-'):
		converted_issue_number = '-'
	else:
		converted_issue_number = ''
	dot = True
	for c in issue_number:
		if c in digits:
			converted_issue_number += c

		else:
			if dot:
				converted_issue_number += '.'
				dot = False

			if c == '½':
				converted_issue_number += '5'

			elif c in alphabet:
				converted_issue_number += alphabet.get(c, alphabet['z'])

	if converted_issue_number:
		return float(converted_issue_number)
	return

def process_issue_number(issue_number: str) -> Union[float, Tuple[float, float], None]:
	"""Convert an issue number or issue range to a (tuple of) float

	Args:
		issue_number (str): The issue number

	Returns:
		Union[float, Tuple[float, float], None]: Either a float representing the issue number,
		a tuple of floats representing the issue numbers when the original issue number was a range of numbers (e.g. 1a-5b)
		or None if it wasn't succesfull in converting.
	"""
	if '-' in issue_number[1:]:
		entries = issue_number[1:].split('-', 1)
		entries[0] = issue_number[0] + entries[0]
		entries = _calc_float_issue_number(entries[0]), _calc_float_issue_number(entries[1])
		if entries[0] is None:
			if entries[1] is None:
				return None
			return entries[1]
		if entries[1] is None:
			return entries[0]
		return entries

	return _calc_float_issue_number(issue_number)

def extract_filename_data(filepath: str, assume_volume_number: bool=True) -> dict:
	"""Extract data and present in a formatted way from a filename (or title of getcomics page).

	Args:
		filepath (str): The filepath or just filename (or any other unformatted text) to extract from
		assume_volume_number (bool, optional): If no volume number was found, should `1` be assumed? When a series has only one volume, often the volume number isn't included in the filename. Defaults to True.

	Returns:
		dict: The extracted data in a formatted way
	"""	
	logging.debug(f'Extracting filename data: {filepath}')
	series, year, volume_number, special_version, issue_number = None, None, None, None, None
	
	# Determine annual or not
	annual_result = annual_regex.search(basename(filepath))
	annual_folder_result = annual_regex.search(basename(dirname(filepath)))
	annual = not (annual_result and annual_folder_result)

	# Generalise filename
	filepath = (unquote(filepath)
		.replace('+',' ')
		.replace('_',' ')
		.replace('_28','(')
		.replace('_29',')')
		.replace('–', '-')
	)
	if 'Том' in filepath:
		filepath = russian_volume_regex.sub(r'Volume \1', filepath)
		filepath = russian_volume_regex_2.sub(r'Volume \1', filepath)
	if '第' in filepath or '卷' in filepath or '册' in filepath:
		filepath = chinese_volume_regex.sub(r'Volume \1', filepath)
		filepath = chinese_volume_regex_2.sub(r'Volume \1', filepath)
	if '권' in filepath:
		filepath = korean_volume_regex.sub(r'Volume \1', filepath)
	if '巻' in filepath:
		filepath = japanese_volume_regex.sub(r'Volume \1', filepath)

	# Only keep filename
	filename = basename(filepath)

	# Keep stripped version of filename without (), {}, [] and extensions
	clean_filename = strip_filename_regex.sub(lambda m: " " * len(m.group()), filename)
	no_ext_clean_filename = strip_filename_regex_2.sub('', clean_filename)

	# Add space before extension for regex matching
	# If there is no extension, append space to the end
	stripped_filename_temp = strip_filename_regex_2.sub(r' \1', clean_filename)
	if stripped_filename_temp == clean_filename:
		clean_filename += ' '
	else:
		clean_filename = stripped_filename_temp
		
	foldername = basename(dirname(filepath))
	upper_foldername = basename(dirname(dirname(filepath)))

	# Get year
	year_pos, year_end, year_folderpos = 10_000, 10_000, 10_000
	for location in (foldername, filename, upper_foldername):
		year_result = year_regex.search(location)
		if year_result:
			if year is None:
				year = next(y for y in year_result.groups() if y)
			if location == filename:
				year_pos = year_result.start(0)
				year_end = year_result.end(0)
			if location == foldername:
				year_folderpos = year_result.start(0)

	# Get volume number
	volume_end, volume_pos, volume_folderpos = 0, 10_000, 10_000
	volume_result = volume_regex.search(clean_filename)
	if volume_result:
		# Volume number found (e.g. Series Volume 1 Issue 6.ext)
		volume_number = volume_result.group(1)
		volume_pos = volume_result.start(0)
		volume_end = volume_result.end(1)

	# Find volume match in folder for finding series name (or when volume number couldn't be found in filename)
	volume_folder_result = volume_folder_regex.search(foldername)
	if volume_folder_result:
		# Volume number found in folder (e.g. Series Volume 1/Issue 5.ext)
		volume_folderpos = volume_folder_result.start(0)
		if not volume_result:
			volume_number = volume_folder_result.group(1) or volume_folder_result.group(2)

	if not volume_result and not volume_folder_result and assume_volume_number:
		volume_number = '1'

	# Check if it's a special version
	issue_pos, special_pos = 10_000, 10_000
	special_result = special_version_regex.search(filename)
	if special_result:
		special_version = special_result.group(1).lower().replace(' ', '-')
		special_pos = special_result.start(0)

	else:
		# No special version so find issue number
		pos_options = (
			({'pos': volume_end},
				(issue_regex, issue_regex_2, issue_regex_3, issue_regex_4, issue_regex_5, issue_regex_6)),
			({'endpos': volume_pos},
				(issue_regex, issue_regex_2, issue_regex_3, issue_regex_4, issue_regex_5))
		)
		for pos_option, regex_list in pos_options:
			for regex in regex_list:
				r = list(regex.finditer(filename, **pos_option))
				if r:
					r.sort(key=lambda e: (int(e.group(1)[-1] not in '0123456789'), 1 / e.start(0) if e.start(0) else 0))

					for result in r:
						if not (year_pos <= result.start(0) <= year_end
						or year_pos <= result.end(0) <= year_end):
							# Issue number found
							issue_number = result.group(1)
							issue_pos = result.start(0)
							break
					else:
						continue
					break
			else:
				continue
			break

		else:
			issue_result = issue_regex_7.search(no_ext_clean_filename)
			if issue_result:
				# Issue number found. File starts with issue number (e.g. Series/Volume N/{issue_number}.ext)
				issue_number = issue_result.group(1)
				issue_pos = issue_result.start(0)
				
		if filename.endswith(image_extensions):
			issue_number = None

	if not issue_number and not special_version:
		special_version = 'tpb'

	# Get series
	series_pos = min(year_pos, volume_pos, issue_pos, special_pos)
	if series_pos:
		# Series name is assumed to be in the filename, left of all other information
		series = no_ext_clean_filename[:series_pos - 1]
	else:
		series_folder_pos = min(year_folderpos, volume_folderpos)
		if series_folder_pos:
			# Series name is assumed to be in the foldername, left of all other information
			series = foldername[:series_folder_pos - 1]
		else:
			# Series name is assumed to be the upper foldername
			series = strip_filename_regex.sub('', upper_foldername)
	series = series_regex.sub('', series)

	# Format output
	if volume_number:
		if volume_number.isdigit():
			volume_number = int(volume_number)
		else:
			i_count = volume_number.lower().count('i')
			if i_count == len(volume_number):
				volume_number = i_count

	calculated_issue_number = process_issue_number(issue_number) if issue_number else issue_number
	year = int(year) if year else year

	file_data = {
		'series': series,
		'year': year,
		'volume_number': volume_number,
		'special_version': special_version,
		'issue_number': calculated_issue_number,
		'annual': annual
	}
		
	logging.debug(f'Extracting filename data: {file_data}')

	return file_data

def folder_path(*folders) -> str:
	"""Turn filepaths relative to the project folder into absolute paths

	Returns:
		str: The absolute filepath
	"""
	return join(dirname(dirname(abspath(__file__))), *folders)

def _list_files(folder: str, ext: list=[]) -> List[str]:
	"""List all files in a folder recursively with absolute paths

	Args:
		folder (str): The root folder to search through
		ext (list, optional): File extensions to only include (give WITH preceding `.`). Defaults to [].

	Returns:
		List[str]: The paths of the files in the folder
	"""
	files = []
	for f in scandir(folder):
		if f.is_dir():
			files += _list_files(f.path, ext)

		elif f.is_file():
			if (not f.name.startswith('.')
			and (
				not ext
				or splitext(f.name)[1].lower() in ext
			)):
				files.append(f.path)

	return files

def _add_file(filepath: str) -> int:
	"""Register a file in the database

	Args:
		filepath (str): The file to register

	Returns:
		int: The id of the entry in the database
	"""	
	logging.debug(f'Adding file to the database: {filepath}')
	cursor = get_db()
	cursor.execute(
		"INSERT OR IGNORE INTO files(filepath, size) VALUES (?,?)",
		(filepath, stat(filepath).st_size)
	)
	file_id = cursor.execute(
		"SELECT id FROM files WHERE filepath = ? LIMIT 1",
		(filepath,)
	).fetchone()[0]
	return file_id

def scan_files(volume_data: dict) -> None:
	"""Scan inside the volume folder for files and map them to issues

	Args:
		volume_data (dict): The output from volumes.Volume().get_info().
	"""	
	logging.debug(f'Scanning for files for {volume_data["id"]}')
	cursor = get_db()

	if not isdir(volume_data['folder']):
		root_folder = RootFolders().get_one(volume_data['root_folder'])['folder']
		create_volume_folder(root_folder, volume_data['id'])

	file_to_issue_map = []
	volume_files = _list_files(folder=volume_data['folder'], ext=supported_extensions)
	for file in volume_files:
		file_data = extract_filename_data(file)

		# Check if file matches volume
		if not (
		(
			(
				file_data['volume_number'] is not None
				and file_data['volume_number'] in (
					volume_data['volume_number'], volume_data['year']
				)
			)
			or (
				file_data['year'] is not None
				and file_data['year'] == volume_data['year']
			)
		)
		and
		(
			file_data['special_version'] == volume_data['special_version']
			or (
				volume_data['special_version'] == 'hard-cover'
				and file_data['special_version'] == 'tpb'
			)
		)):
			continue

		# If file is special version, it means it covers all issues in volume so add it to every issue
		if file_data['special_version']:
			# Add file to database if it isn't registered yet
			file_id = _add_file(file)
			
			file_to_issue_map.append([file_id, volume_data['issues'][0]['id']])

		# Search for issue number
		elif file_data['issue_number'] is not None:
			if isinstance(file_data['issue_number'], tuple):
				issue_ids = cursor.execute("""
					SELECT id
					FROM issues
					WHERE
						volume_id = ?
						AND ? <= calculated_issue_number
						AND calculated_issue_number <= ?;
					""",
					(volume_data['id'], *file_data['issue_number'])
				).fetchall()
				if issue_ids:
					# Matching issue(s) found
					file_id = _add_file(file)
					for issue_id in issue_ids:
						file_to_issue_map.append([file_id, issue_id[0]])

			else:
				issue_id = cursor.execute("""
					SELECT id
					FROM issues
					WHERE
						volume_id = ?
						AND calculated_issue_number = ?
					LIMIT 1;
					""",
					(volume_data['id'], file_data['issue_number'])
				).fetchone()
				if issue_id:
					# Matching issue found
					file_id = _add_file(file)
					file_to_issue_map.append([file_id, issue_id[0]])

	# Delete all file bindings for the volume
	cursor.execute("""
		DELETE FROM issues_files
		WHERE rowid IN (
			SELECT if.rowid
			FROM issues_files if
			INNER JOIN issues i
			ON i.id = if.issue_id
			WHERE i.volume_id = ?
		);
		""",
		(volume_data['id'],)
	)

	if file_to_issue_map:
		# Add new file bindings
		cursor.executemany(
			"INSERT INTO issues_files(file_id, issue_id) VALUES (?,?)",
			file_to_issue_map
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

def delete_empty_folders(top_folder: str, root_folder: str) -> None:
	"""Keep deleting empty folders until we reach a folder with content or the root folder

	Args:
		top_folder (str): The folder to start deleting from
		root_folder (str): The root folder to stop at in case we reach it
	"""
	logging.debug(f'Deleting folders from {top_folder} until {root_folder}')

	if not top_folder.startswith(abspath(root_folder) + sep):
		logging.error(f'The folder {top_folder} is not in {root_folder}')
		return
		
	while (not exists(top_folder) or not(
		samefile(top_folder, root_folder)
		or listdir(top_folder)
	)):
		if not exists(top_folder):
			top_folder = dirname(top_folder)
			continue

		logging.debug(f'Deleting folder: {top_folder}')
		rmtree(top_folder, ignore_errors=True)
		top_folder = dirname(top_folder)
	return

def create_volume_folder(root_folder: str, volume_id: int, volume_folder: str=None) -> str:
	"""Generate, register and create a folder for a volume

	Args:
		root_folder (str): The rootfolder (path, not id)
		volume_id (int): The id of the volume for which the folder is
		volume_folder (str, optional): Custom volume folder. Defaults to None.

	Returns:
		str: The path to the folder
	"""	
	# Generate and register folder
	if volume_folder is None:
		from backend.naming import generate_volume_folder_name

		volume_folder = join(
			root_folder, generate_volume_folder_name(volume_id)
		)
	else:
		from backend.naming import _make_filename_safe
		volume_folder = join(
			root_folder, _make_filename_safe(volume_folder)
		)
	get_db().execute(
		"UPDATE volumes SET folder = ? WHERE id = ?",
		(volume_folder, volume_id)
	)

	# Create folder if it doesn't exist
	makedirs(volume_folder, exist_ok=True)

	return volume_folder

def move_volume_folder(volume_id: int, new_root_folder: int, new_volume_folder: str) -> str:
	"""Move a volume to a new folder

	Args:
		volume_id (int): The id of the volume to move the folder for
		new_root_folder (int): The id of the new desired root folder
		new_volume_folder (str): The new desired volume folder

	Returns:
		str: The new location of the volume folder
	"""
	cursor = get_db()
	current_folder, current_root_folder, custom_folder = cursor.execute("""
		SELECT v.folder, rf.folder, v.custom_folder
		FROM volumes v
		INNER JOIN root_folders rf
		ON v.root_folder = rf.id
		WHERE v.id = ?
		LIMIT 1;
		""",
		(volume_id,)
	).fetchone()
	current_volume_folder = relpath(current_folder, current_root_folder)
	
	# If new_volume_folder is empty or None, generate default folder and unset custom folder
	if not new_volume_folder:
		from backend.naming import generate_volume_folder_name
		cursor.execute(
			"UPDATE volumes SET custom_folder = 0 WHERE id = ?",
			(volume_id,)
		)
		new_volume_folder = generate_volume_folder_name(volume_id)

	# Not custom folder set + new_volume_folder is different
	# 	-> setting custom folder for the first time so mark volume for custom folder
	elif not custom_folder and new_volume_folder != current_volume_folder:
		cursor.execute(
			"UPDATE volumes SET custom_folder = 1 WHERE id = ?",
			(volume_id,)
		)

	from backend.naming import _make_filename_safe
	new_root_folder = RootFolders().get_one(new_root_folder)['folder']
	new_volume_folder = _make_filename_safe(new_volume_folder)

	new_folder = abspath(join(new_root_folder, new_volume_folder))

	# Create and move to new folder
	logging.info(f'Moving volume folder from {current_folder} to {new_folder}')
	cursor.execute("""
			SELECT DISTINCT
				f.filepath
			FROM files f
			INNER JOIN issues_files if
			INNER JOIN issues i
			ON
				i.id = if.issue_id
				AND if.file_id = f.id
			WHERE i.volume_id = ?;
			""",
			(volume_id,)
	)
	renamed_files = [(join(new_folder, relpath(filepath[0], current_folder)), filepath[0]) for filepath in cursor]
	cursor.executemany(
		"UPDATE files SET filepath = ? WHERE filepath = ?;",
		renamed_files
	)

	makedirs(new_folder, 0o664, exist_ok=True)
	for new_filepath, old_filepath in renamed_files:
		move(old_filepath, new_filepath)

	# Delete old folder
	if not (new_folder + sep).startswith(current_folder.rstrip(sep) + sep):
		delete_empty_folders(current_folder, current_root_folder)

	return new_folder

def delete_volume_folder(volume_id: int) -> None:
	"""Delete the volume folder including it's contents,
	then start deleting parent folders when they're also empty,
	until either a parent folder is found with other content or the
	root folder is reached.

	Args:
		volume_id (int): The id of the volume for which to delete it's folder.
	"""
	logging.info(f'Deleting volume folder of {volume_id}')
	cursor = get_db()

	# Delete volume files
	cursor.execute("""
		SELECT DISTINCT
			f.filepath
		FROM files f
		INNER JOIN issues_files if
		INNER JOIN issues i
		ON
			i.id = if.issue_id
			AND if.file_id = f.id
		WHERE i.volume_id = ?;
		""",
		(volume_id,)
	)
	for filepath in cursor:
		remove(filepath[0])

	folder, root_folder = cursor.execute(
		"""
		SELECT
			volumes.folder, root_folders.folder
		FROM
			volumes, root_folders
		WHERE
			volumes.root_folder = root_folders.id
			AND volumes.id = ?
		LIMIT 1;
		""",
		(volume_id,)
	).fetchone()
	
	delete_empty_folders(folder, root_folder)
	return
	
def rename_file(before: str, after: str) -> None:
	"""Rename a file, taking care of new folder locations

	Args:
		before (str): The current filepath of the file
		after (str): The new desired filepath of the file
	"""
	logging.debug(f'Renaming file {before} to {after}')
	# Create destination folder
	makedirs(dirname(after), exist_ok=True)
	
	# Move file into folder
	move(before, after)
	return
