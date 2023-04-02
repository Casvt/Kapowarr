#-*- coding: utf-8 -*-

"""This file contains function regarding files and integrating them into Kapowarr

extract_filename_data is inspired by the file parsing of Kavita and Comictagger:
	https://github.com/Kareadita/Kavita/blob/develop/API/Services/Tasks/Scanner/Parser/Parser.cs
	https://github.com/comictagger/comictagger/blob/develop/comicapi/filenameparser.py
"""

import logging
from os import listdir, makedirs, scandir, stat
from os.path import (abspath, basename, dirname, join, relpath, samefile,
                     splitext)
from re import IGNORECASE, compile
from shutil import move, rmtree
from typing import List, Tuple, Union
from urllib.parse import unquote

from backend.db import get_db

alphabet = 'abcdefghijklmnopqrstuvwxyz'
supported_extensions = ('.png','.jpeg','.jpg','.webp','.gif','.cbz','.zip','.rar','.cbr','.tar.gz','.7zip','.7z','.cb7','.cbt','.epub','.pdf')
file_extensions = r'\.(' + '|'.join(e[1:] for e in supported_extensions) + r')$'
volume_regex_snippet = r'(?:v(?:ol|olume)?)(?:\.\s|[\.\-\s])?(\d+|I{1,3})'
year_regex_snippet = r'(?:(\d{4})(?:-\d{2}){0,2}|(\d{4})-\d{4}|(?:\d{2}-){1,2}(\d{4})|(\d{4})[\s\.\-]Edition|(\d{4})-\d{4}\s{3}\d{4})'

# Cleaning the filename
strip_filename_regex = compile(r'\(.*?\)|\[.*?\]|\{.*?\}', IGNORECASE)
strip_filename_regex_2 = compile(file_extensions, IGNORECASE)

# Supporting languages by translating them
russian_volume_regex = compile(r'Томa?[\s\.]?(\d+)', IGNORECASE)
russian_volume_regex_2 = compile(r'(\d+)[\s\.]?Томa?', IGNORECASE)
chinese_volume_regex = compile(r'第(\d+)(?:卷|册)', IGNORECASE)
chinese_volume_regex_2 = compile(r'(?:卷|册)(\d+)', IGNORECASE)
korean_volume_regex = compile(r'제?(\d+)권', IGNORECASE)
japanese_volume_regex = compile(r'(\d+(?:\-\d+)?)巻', IGNORECASE)

# Extract data from (stripped)filename
special_version_regex = compile(r'(?:\b|\()(tpb|os|one\-shot|ogn|gn)(?:\b|\))', IGNORECASE)
volume_regex = compile(volume_regex_snippet, IGNORECASE)
volume_folder_regex = compile(r'^(\d+)$|' + volume_regex_snippet, IGNORECASE)
series_folder_regex = compile(r'(^.*)(?= ' + volume_regex_snippet + r')', IGNORECASE)
issue_regex = compile(r'(?:c(?:hapter)?|issue)s?[\s\-\.]?#?(\d+(?:\.\d{1,2})?(?:[\s\.]?\-[\s\.]?\d+(?:\.\d{1,2})?)?)', IGNORECASE)
issue_regex_2 = compile(r'#(\d+(?:\.\d{1,2})?)[\s\.](?!(\-[\s\.]?|\d+))')
issue_regex_3 = compile(r'#?(\d+(?:\.\d{1,2})?[\s\.]?-[\s\.]?\d+(?:\.\d{1,2})?)[\s\.]')
issue_regex_4 = compile(r'(?:\s|\-|\.)(\d+(?:\.\d{1,2})?)(?:\s|\-|\.)')
issue_regex_5 = compile(r'^(\d+(?:\.\d{1,2})?)$')
year_regex = compile(r'\(' + year_regex_snippet + r'\)|--' + year_regex_snippet + r'--|, ' + year_regex_snippet + r'\s{3}', IGNORECASE)

def process_issue_number(issue_number: str) -> Union[float, Tuple[float, float], None]:
	logging.debug(f'Processing issue number: {issue_number}')
	if '-' in issue_number and not issue_number.startswith('-'):
		entries = issue_number.split('-')
	else:
		entries = (issue_number,)

	result = []
	for entry in entries:
		entry = entry.replace(',','.').rstrip('.')
		try:
			# Targets numbers that are already valid float numbers, just in string form
			result.append(float(entry))
			continue
		except ValueError:
			pass
		
		# Issue has special number notation
		converted_issue_number = ''
		for c in list(entry):
			if c.isdigit():
				converted_issue_number += c

			else:
				if not '.' in converted_issue_number:
					converted_issue_number += '.'

				if c == '½':
					converted_issue_number += '5'

				elif c in alphabet:
					converted_issue_number += str(int(
						(alphabet.index(c) + 1) / 0.26
					)).zfill(3)

		try:
			result.append(float(converted_issue_number))
		except ValueError:
			pass
	
	if result:
		if len(result) == 1:
			result = result[0]
		else:
			result = tuple(result)
	else:
		result = None
	logging.debug(f'Processing issue number: {result}')
	return result

def extract_filename_data(file: str, assume_volume_number: bool=True) -> dict:
	logging.debug(f'Extracting filename data: {file}')
	series, year, volume_number, special_version, issue_number = None, None, None, None, None

	#generalise filename
	file = file.replace('+',' ').replace('_',' ')
	if 'Том' in file:
		file = russian_volume_regex.sub(r'Volume \1', file)
		file = russian_volume_regex_2.sub(r'Volume \1', file)
	if '第' in file or '卷' in file or '册' in file:
		file = chinese_volume_regex.sub(r'Volume \1', file)
		file = chinese_volume_regex_2.sub(r'Volume \1', file)
	if '권' in file:
		file = korean_volume_regex.sub(r'Volume \1', file)
	if '巻' in file:
		file = japanese_volume_regex.sub(r'Volume \1', file)
	#only keep filename
	filename = unquote(basename(file))
	#fix some inconsistencies
	filename = filename.replace('_28','(').replace('_29',')').replace('–', '-')
	
	#keep stripped version of filename without (), {}, [] and extensions
	stripped_filename = strip_filename_regex.sub(lambda m: " " * len(m.group()), filename)
	fully_stripped_filename = strip_filename_regex_2.sub('', stripped_filename)
	stripped_filename_temp = strip_filename_regex_2.sub(r' \1', stripped_filename)
	if stripped_filename_temp == stripped_filename:
		stripped_filename += ' '
	else:
		stripped_filename = stripped_filename_temp

	#get volume number
	volume_result = volume_regex.search(stripped_filename)
	if volume_result:
		#volume number found (e.g. Series Volume 1.ext)
		volume_number = volume_result.group(1)
		volume_pos = volume_result.end(1)
		#because volume was found in filename, try to find series name in filename too
		if volume_result.start(0) > 0:
			#series found (e.g. Series Volume 1.ext)
			series = stripped_filename[:volume_result.start(0) - 1].strip()

	else:
		#no volume number found; check if folder name is volume number
		volume_result = volume_folder_regex.search(basename(dirname(file)))
		volume_pos = 0
		if volume_result:
			#volume number found in folder name (e.g. Series Volume 1/Issue 1.ext); assume series is also in folder name
			volume_number = volume_result.group(1) or volume_result.group(2)
		else:
			#no volume number found in folder name so assume that folder name is series name
			series = strip_filename_regex.sub('', basename(dirname(file))).strip() or None
			if assume_volume_number:
				volume_number = 1

	#check if it's a special version
	special_result = special_version_regex.search(filename)
	if special_result:
		special_version = special_result.group(1).lower()
		if special_result.start(0) > 0 and series == None:
			series = stripped_filename[:special_result.start(1) - 1].strip()
	else:
		#no special version so find issue number; assume to the right of volume number (if found)
		for regex in (issue_regex, issue_regex_2, issue_regex_3, issue_regex_4):
			issue_result = regex.search(stripped_filename, pos=volume_pos)
			if issue_result:
				#issue number found
				issue_number = issue_result.group(1)
				if (
					not series
					and issue_result.start(0) > 0
					and ((volume_result != None
							and volume_result.start(0) > 0)
						or volume_result == None
					)
				):
					#series name is probably left of issue number (no volume number found)
					series = stripped_filename[:issue_result.start(0) - 1].strip()
				break
		else:
			issue_result = issue_regex_5.search(fully_stripped_filename)
			if issue_result:
				issue_number = issue_result.group(1)
	
	if not series:
		#series +? volume number in folder name or series name in upper folder name
		if volume_folder_regex.search(basename(dirname(file))):
			#volume number in folder name
			series_result = series_folder_regex.search(basename(dirname(file)))
			if series_result:
				series = series_result.group(0) or None
			if not series:
				#series name is in upper folder name
				series = strip_filename_regex.sub('', basename(dirname(dirname(file)))).strip()
		else:
			#no volume number in folder name so it's series name
			series = strip_filename_regex.sub('', basename(dirname(file))).strip()

	#get year
	year_result = year_regex.search(filename)
	if year_result:
		#year found
		for y in year_result.groups():
			if y is not None:
				year = y
				break
	else:
		year_result = year_regex.search(basename(dirname(file)))
		if year_result:
			#year found in upper folder
			for y in year_result.groups():
				if y is not None:
					year = y
					break
		else:
			year_result = year_regex.search(basename(dirname(dirname(file))))
			if year_result:
				#year found in upper upper folder
				for y in year_result.groups():
					if y is not None:
						year = y
						break

	if issue_number == None and special_version == None:
		special_version = 'tpb'
		#because file is special version, series name is probably just complete filename
		if not series:
			series = stripped_filename.replace('  ', ' ').strip()

	#format output
	if isinstance(volume_number, str):
		if volume_number.isdigit():
			volume_number = int(volume_number)

		elif volume_number.lower().count('i') == len(volume_number):
			volume_number = volume_number.lower().count('i')

	calculated_issue_number = process_issue_number(issue_number) if issue_number else issue_number
	year = int(year) if year else year

	file_data = {
		'series': series,
		'year': year,
		'volume_number': volume_number,
		'special_version': special_version,
		'issue_number': calculated_issue_number
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
		ext (list, optional): File extensions to only include (give WITH preceding '.'). Defaults to [].

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
	cursor = get_db()

	file_to_issue_map = []
	volume_files = _list_files(folder=volume_data['folder'], ext=supported_extensions)
	for file in volume_files:
		file_data = extract_filename_data(file)

		# Check if file matches volume
		if (file_data['volume_number'] is not None
		and file_data['volume_number'] != volume_data['volume_number']):
			continue

		# If file is special version, it means it covers all issues in volume so add it to every issue
		if file_data['special_version']:
			# Add file to database if it isn't registered yet
			file_id = _add_file(file)
			
			# Add file to every issue
			for issue in volume_data['issues']:
				file_to_issue_map.append([file_id, issue['id']])

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
			INNER JOIN issues_files if
			ON f.id = if.file_id
			WHERE if.file_id IS NULL
		);
	""")

	return

def create_volume_folder(root_folder: str, volume_id: int) -> str:
	from backend.naming import generate_volume_folder_name

	# Generate and register folder
	volume_folder = join(
		root_folder, generate_volume_folder_name(volume_id)
	)
	get_db().execute(
		"UPDATE volumes SET folder = ? WHERE id = ?",
		(volume_folder, volume_id)
	)

	# Create folder if it doesn't exist
	makedirs(volume_folder, exist_ok=True)

	return volume_folder

def move_volume_folder(folder: str, root_folder: str, new_root_folder: str) -> str:
	# Generate new folder path
	new_folder = abspath(join(
		new_root_folder, relpath(folder, root_folder))
	)
	
	# Create and move to new folder
	move(folder, new_folder)

	return new_folder

def delete_volume_folder(volume_id: int) -> None:
	folder, root_folder = get_db().execute(
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
	
	# Keep deleting empty folders until
	# we reach a folder with content or the root folder
	while (not samefile(folder, root_folder)
	and not len(listdir(folder))):
		rmtree(folder, ignore_errors=True)
		folder = dirname(folder)
	return
	
def rename_file(before: str, after: str) -> None:
	# Create destination folder
	makedirs(dirname(after), exist_ok=True)
	
	# Move file into folder
	move(before, after)
	return
