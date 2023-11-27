#-*- coding: utf-8 -*-

"""This file contains functions regarding the (re)naming of folders and media
"""

import logging
from os import listdir
from os.path import basename, dirname, isdir, isfile, join, splitext
from re import IGNORECASE, compile, escape, match
from string import Formatter
from typing import Dict, List, Tuple, Union

from backend.custom_exceptions import (InvalidSettingValue, IssueNotFound,
                                       VolumeNotFound)
from backend.db import get_db
from backend.files import delete_empty_folders, image_extensions, rename_file
from backend.settings import Settings

formatting_keys = (
	'series_name',
	'clean_series_name',
	'volume_number',
	'comicvine_id',
	'year',
	'publisher'
)

issue_formatting_keys = formatting_keys + (
	'issue_comicvine_id',
	'issue_number',
	'issue_title',
	'issue_release_date',
	'issue_release_year'
)

filename_cleaner = compile(r'(<|>|:|\"|\||\?|\*|\x00|(\s|\.)+$)')
page_regex = compile(r'^(\d+)$|page[\s\.\-]?(\d+)', IGNORECASE)
page_regex_2 = compile(r'(\d+)')

#=====================
# Name generation
#=====================
def _make_filename_safe(unsafe_filename: str) -> str:
	"""Make a filename safe to use in a filesystem. It removes illegal characters.

	Args:
		unsafe_filename (str): The filename to be made safe.

	Returns:
		str: The filename, now with characters removed/replaced
		so that it's filesystem-safe.
	"""
	safe_filename = filename_cleaner.sub('', unsafe_filename)
	return safe_filename

def _get_formatting_data(
	volume_id: int,
	issue_id: int=None,
	_volume_data: dict=None,
	_volume_number: Union[int, Tuple[int, int], None]=None
) -> dict:
	"""Get the values of the formatting keys for a volume or issue

	Args:
		volume_id (int): The id of the volume

		issue_id (int, optional): The id of the issue.
			Defaults to None.

		_volume_data (dict, optional): Instead of fetching data based on
		the volume id, work with the data given in this variable.
			Defaults to None.

		_volume_number (Union[int, Tuple[int, int], None], optional):
		Override the volume number.
			Defaults to None.

	Raises:
		VolumeNotFound: The volume id doesn't map to any volume in the library
		IssueNotFound: The issue id doesn't map to any issue in the volume

	Returns:
		dict: The formatting keys and their values for the item
	"""
	# Fetch volume data and check if id is valid
	cursor = get_db('dict')
	if _volume_data is None:
		volume_data = cursor.execute("""
			SELECT
				comicvine_id,
				title, year, publisher,
				volume_number
			FROM volumes
			WHERE id = ?
			LIMIT 1;
		""", (volume_id,)).fetchone()
		
		if not volume_data:
			raise VolumeNotFound
		volume_data = dict(volume_data)
	else:
		volume_data = _volume_data
	
	if _volume_number is not None:
		volume_data['volume_number'] = _volume_number
	
	# Build formatted data
	if volume_data.get('title').startswith('The '):
		clean_title = volume_data.get('title') + ', The'
	elif volume_data.get('title').startswith('A '):
		clean_title = volume_data.get('title') + ', A'
	else:
		clean_title = volume_data.get('title') or 'Unknown'

	s = Settings().get_settings()
	volume_padding = s['volume_padding']
	issue_padding = s['issue_padding']

	if not isinstance(volume_data.get('volume_number'), tuple):
		volume_number = (str(volume_data.get('volume_number'))
			.zfill(volume_padding))
	
	else:
		volume_number = ' - '.join((
			str(n).zfill(volume_padding)
			for n in volume_data['volume_number']
		))

	formatting_data = {
		'series_name': ((volume_data.get('title') or 'Unknown')
			.replace('/', '')
			.replace(r'\\', '')
		),
		'clean_series_name': (clean_title
			.replace('/', '')
			.replace(r'\\', '')
		),
		'volume_number': volume_number,
		'comicvine_id': volume_data.get('comicvine_id') or 'Unknown',
		'year': volume_data.get('year') or 'Unknown',
		'publisher': volume_data.get('publisher') or 'Unknown'
	}
	
	if issue_id:
		# Add issue data if issue is found
		issue_data = cursor.execute("""
			SELECT
				comicvine_id,
				issue_number,
				title, date
			FROM issues
			WHERE id = ?;
		""", (issue_id,)).fetchone()
		
		if not issue_data:
			raise IssueNotFound
		issue_data = dict(issue_data)
			
		formatting_data.update({
			'issue_comicvine_id': issue_data.get('comicvine_id') or 'Unknown',
			'issue_number': (
				str(issue_data.get('issue_number'))
					.zfill(issue_padding) 
				or 'Unknown'
			),
			'issue_title': ((issue_data.get('title') or 'Unknown')
				.replace('/', '')
				.replace(r'\\', '')
			),
			'issue_release_date': issue_data.get('date') or 'Unknown',
			'issue_release_year': ((issue_data.get('date') or '')
					.split('-')[0]
				or 'Unknown'
			)
		})
		
	return formatting_data

def generate_volume_folder_name(volume_id: int, _volume_data: dict=None) -> str:
	"""Generate a volume folder name based on the format string

	Args:
		volume_id (int): The id of the volume for which to generate the string

		_volume_data (dict, optional): Instead of fetching data based on
		the volume id, work with the data given in this variable.
			Defaults to None.

	Returns:
		str: The volume folder name
	"""
	formatting_data = _get_formatting_data(volume_id, None, _volume_data)
	format: str = Settings().get_settings()['volume_folder_naming']

	name = format.format(**formatting_data)
	save_name = _make_filename_safe(name)
	return save_name

def generate_tpb_name(
	volume_id: int,
	_volume_number: Union[int, Tuple[int, int], None] = None
) -> str:
	"""Generate a TPB name based on the format string

	Args:
		volume_id (int): The id of the volume for which to generate the string.

		_volume_number (Union[int, Tuple[int, int], None], optional):
		Override the volume number.
			Defaults to None.

	Returns:
		str: The TPB name
	"""
	formatting_data = _get_formatting_data(
		volume_id,
		_volume_number=_volume_number
	)
	format: str = Settings().get_settings()['file_naming_tpb']

	name = format.format(**formatting_data)
	save_name = _make_filename_safe(name)
	return save_name

def generate_empty_name(
	volume_id: int,
	_volume_number: Union[int, Tuple[int, int], None] = None
) -> str:
	"""Generate a name without issue number or TPB marking

	Args:
		volume_id (int): The id of the volume for which to generate the string.

		_volume_number (Union[int, Tuple[int, int], None], optional):

		Override the volume number.
			Defaults to None.

	Returns:
		str: The empty name
	"""
	save_tpb_name = generate_tpb_name(volume_id, _volume_number)
	save_name = save_tpb_name.replace('tpb', '').replace('TPB', '').strip()
	return save_name

def generate_issue_range_name(
	volume_id: int,
	calculated_issue_number_start: float,
	calculated_issue_number_end: float
) -> str:
	"""Generate an issue range name based on the format string

	Args:
		volume_id (int): The id of the volume of the issues

		calculated_issue_number_start (float): The start of the issue range.
			Output of `files.process_issue_number()`.

		calculated_issue_number_end (float): The end of the issue range.
			Output of `files.process_issue_number()`.

	Returns:
		str: The issue range name
	"""
	cursor = get_db()
	issue_id = cursor.execute("""
		SELECT id
		FROM issues
		WHERE volume_id = ?
			AND calculated_issue_number = ?
		LIMIT 1;
	""", (volume_id, calculated_issue_number_start)).fetchone()[0]
	formatting_data = _get_formatting_data(volume_id, issue_id)
	settings = Settings().get_settings()

	if (formatting_data['issue_title'] == 'Unknown'
		or (
			settings['volume_as_empty']
			and formatting_data['issue_title'].lower().startswith('volume ')
		)):
		format: str = settings['file_naming_empty']
	else:
		format: str = settings['file_naming']

	# Override issue number to range
	issue_number_start, issue_number_end = cursor.execute("""
		SELECT issue_number
		FROM issues
		WHERE
			volume_id = ?
			AND
			(
				calculated_issue_number = ?
				OR calculated_issue_number = ?
			)
		ORDER BY calculated_issue_number
		LIMIT 2;
		""",
		(volume_id,
		calculated_issue_number_start,
		calculated_issue_number_end)
	).fetchall()
	formatting_data['issue_number'] = (
		str(issue_number_start[0])
			.zfill(settings['issue_padding'])
		+ ' - ' +
		str(issue_number_end[0])
			.zfill(settings['issue_padding'])
	)

	name = format.format(**formatting_data)
	save_name = _make_filename_safe(name)
	return save_name

def generate_issue_name(volume_id: int, calculated_issue_number: float) -> str:
	"""Generate a issue name based on the format string

	Args:
		volume_id (int): The id of the volume of the issue

		calculated_issue_number (float): The issue number.
			Output of `files.process_issue_number()`.

	Returns:
		str: The issue name
	"""	
	issue_id = get_db().execute("""
		SELECT id
		FROM issues
		WHERE volume_id = ?
			AND calculated_issue_number = ?
		LIMIT 1;
	""", (volume_id, calculated_issue_number)).fetchone()[0]
	formatting_data = _get_formatting_data(volume_id, issue_id)
	settings = Settings().get_settings()

	if (formatting_data['issue_title'] == 'Unknown'
		or (
			settings['volume_as_empty']
			and formatting_data['issue_title'].lower().startswith('volume ')
		)):
		format: str = settings['file_naming_empty']
	else:
		format: str = settings['file_naming']

	name = format.format(**formatting_data)
	save_name = _make_filename_safe(name)
	return save_name

#=====================
# Checking formats
#=====================
def check_format(format: str, type: str) -> None:
	"""Check if a format string is valid

	Args:
		format (str): The format string to check
		type (str): What type of format string it is
			Options: 'file_naming', 'file_naming_tpb', 'folder_naming'

	Raises:
		InvalidSettingValue: Something in the string is invalid
	"""	
	keys = [fn for _, fn, _, _ in Formatter().parse(format) if fn is not None]

	if type in ('file_naming', 'file_naming_tpb', 'file_naming_empty'):
		if r'/' in format or r'\\' in format:
			raise InvalidSettingValue(type, format)

		if type == 'file_naming_tpb':
			naming_keys = formatting_keys
		else:
			naming_keys = issue_formatting_keys

	else:
		naming_keys = formatting_keys

	for format_key in keys:
		if not format_key in naming_keys:
			raise InvalidSettingValue(type, format)

	return

#=====================
# Renaming
#=====================
def same_name_indexing(
	suggested_name: str,
	current_name: str,
	folder: str,
	planned_names: List[Dict[str, str]]
) -> str:
	"""Add a number after a filename if the filename already exists.

	Args:
		suggested_name (str): The currently suggested filename
		current_name (str): The current name of the file
		folder (str): The folder that the file is in
		planned_names (List[Dict[str, str]]): The already planned names of
		other files.

	Returns:
		str: The suggested name, now with number at the end if needed
	"""
	same_names = tuple(
		filter(
			lambda r: match(escape(suggested_name) + r'( \(\d+\))?$', r),
			[splitext(basename(r['after']))[0] for r in planned_names]
		)
	)
	if isdir(folder):
		# Add number to filename if an other file has the same name
		basename_file = splitext(basename(current_name))[0]
		same_names += tuple(
			filter(
				lambda f: (
					not f == basename_file
					and match(
						escape(suggested_name) + r'(?: \(\d+\))?$',
						f
					)
				),
				[splitext(f)[0] for f in listdir(folder)]
			)
		)

	if same_names:
		i = 0
		while True:
			if not i and not suggested_name in same_names:
				break
			if i and not f"{suggested_name} ({i})" in same_names:
				suggested_name += f" ({i})"
				break
			i += 1

	return suggested_name

def preview_mass_rename(
	volume_id: int,
	issue_id: int=None,
	filepath_filter: List[str]=None
) -> List[Dict[str, str]]:
	"""Preview what naming.mass_rename() will do.

	Args:
		volume_id (int): The id of the volume for which to check the renaming.

		issue_id (int, optional): The id of the issue for which to check the renaming.
			Defaults to None.

		filepath_filter (List[str], optional): Only process files that are in the list.
			Defaults to None.

	Returns:
		List[Dict[str, str]]: The renaming proposals.
	"""
	result = []
	cursor = get_db('dict')
	# Fetch all files linked to the volume or issue
	if not issue_id:
		file_infos = cursor.execute("""
			SELECT DISTINCT
				f.id, f.filepath
			FROM files f
			INNER JOIN issues_files if
			INNER JOIN issues i
			ON
				i.id = if.issue_id
				AND if.file_id = f.id
			WHERE i.volume_id = ?
			ORDER BY f.filepath;
			""",
			(volume_id,)
		).fetchall()
		root_folder, custom_folder, folder = cursor.execute("""
			SELECT rf.folder, v.custom_folder, v.folder
			FROM
				root_folders rf
				JOIN volumes v
			ON v.root_folder = rf.id
			WHERE v.id = ?
			LIMIT 1;
			""",
			(volume_id,)
		).fetchone()
		if custom_folder == 0:
			folder = join(root_folder, generate_volume_folder_name(volume_id))
	else:
		file_infos = cursor.execute("""
			SELECT
				f.id, f.filepath
			FROM files f
			INNER JOIN issues_files if
			ON if.file_id = f.id
			WHERE if.issue_id = ?
			ORDER BY f.filepath;
			""",
			(issue_id,)
		).fetchall()
		if not file_infos: return result
		folder = dirname(file_infos[0]['filepath'])

	if filepath_filter is not None:
		file_infos = filter(
			lambda f: f['filepath'] in filepath_filter,
			file_infos
		)

	special_version = cursor.execute(
		"SELECT special_version FROM volumes WHERE id = ? LIMIT 1;",
		(volume_id,)
	).fetchone()[0]
	name_volume_as_issue = Settings().get_settings()['volume_as_empty']

	for file in file_infos:
		if not isfile(file['filepath']):
			continue
		logging.debug(f'Renaming: original filename: {file["filepath"]}')
		
		# Find the issues that the file covers
		issues = cursor.execute("""
			SELECT
				calculated_issue_number
			FROM issues
			INNER JOIN issues_files
			ON id = issue_id
			WHERE file_id = ?
			ORDER BY calculated_issue_number;
			""",
			(file['id'],)
		).fetchall()
		if special_version == 'tpb':
			suggested_name = generate_tpb_name(volume_id)

		elif special_version == 'volume-as-issue' and not name_volume_as_issue:
			if len(issues) > 1:
				suggested_name = generate_empty_name(
					volume_id,
					(int(issues[0][0]), int(issues[-1][0]))
				)
			else:
				suggested_name = generate_empty_name(
					volume_id,
					int(issues[0][0])
				)

		elif (special_version or 'volume-as-issue') != 'volume-as-issue':
			suggested_name = generate_empty_name(volume_id)

		elif len(issues) > 1:
			# File covers multiple issues
			suggested_name = generate_issue_range_name(
				volume_id,
				issues[0][0],
				issues[-1][0]
			)
		
		else:
			# File covers one issue
			suggested_name = generate_issue_name(volume_id, issues[0][0])

		# If file is image, it's probably a page instead of a whole issue/tpb.
		# So put it in it's own folder together with the other images.
		if file['filepath'].endswith(image_extensions):
			filename: str = basename(file['filepath'])
			page_number = None
			if 'cover' in filename.lower():
				page_number = 'Cover'
			else:
				page_result = page_regex.search(filename)
				if page_result:
					page_number = next(r for r in page_result.groups() if r is not None)
				else:
					page_result = None
					r = page_regex_2.finditer(basename(file['filepath']))
					for page_result in r: pass
					if page_result:
						page_number = page_result.group(1)
			suggested_name = join(suggested_name, page_number or '1')

		# Add number to filename if other file has the same name
		suggested_name = same_name_indexing(
			suggested_name,
			file['filepath'],
			folder,
			result
		)

		suggested_name = join(
			folder,
			suggested_name + splitext(file["filepath"])[1]
		)

		logging.debug(f'Renaming: suggested filename: {suggested_name}')
		if file['filepath'] != suggested_name:
			logging.debug(f'Renaming: added rename')
			result.append({
				'before': file['filepath'],
				'after': suggested_name
			})
		
	return result

def mass_rename(
	volume_id: int,
	issue_id: int=None,
	filepath_filter: List[str]=None
) -> None:
	"""Carry out proposal of `naming.preview_mass_rename()`.

	Args:
		volume_id (int): The id of the volume for which to rename.

		issue_id (int, optional): The id of the issue for which to rename.
			Defaults to None.

		filepath_filter (List[str], optional): Only rename files that are in the list.
			Defaults to None.
	"""
	cursor = get_db()
	renames = preview_mass_rename(volume_id, issue_id, filepath_filter)

	if not issue_id and renames:
		folders = {
			'before': None,
			'after': None
		}
		for target in folders:
			file = renames[0][target]
			if file.endswith(image_extensions):
				folders[target] = dirname(dirname(file))
			else:
				folders[target] = dirname(file)
		cursor.execute(
			"UPDATE volumes SET folder = ? WHERE id = ?",
			(folders['after'], volume_id)
		)

	for r in renames:
		rename_file(r['before'], r['after'])
		cursor.execute(
			"UPDATE files SET filepath = ? WHERE filepath = ?;",
			(r['after'], r['before'])
		)
	
	if renames:
		root_folder = get_db().execute("""
		   SELECT rf.folder
		   FROM root_folders rf
		   INNER JOIN volumes v
		   ON rf.id = v.root_folder
		   WHERE v.id = ?
		   """,
		   (volume_id,)
		).fetchone()[0]
		delete_empty_folders(folders['before'], root_folder)

	logging.info(
		f'Renamed volume {volume_id} {f"issue {issue_id}" if issue_id else ""}'
	)
	return
