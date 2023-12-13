#-*- coding: utf-8 -*-

from itertools import chain
from os.path import dirname, splitext
from sys import platform
from typing import Dict, List, Set, Union

from backend.converters import FileConverter, rar_executables
from backend.db import get_db
from backend.files import scan_files
from backend.volumes import Volume

conversion_methods: Dict[str, Dict[str, FileConverter]] = {}
"source_format -> target_format -> conversion class"
for fc in FileConverter.__subclasses__():
	conversion_methods.setdefault(fc.source_format, {})[fc.target_format] = fc

def get_available_formats() -> Set[str]:
	"""Get all available formats that can be converted to.

	Returns:
		Set[str]: The list with all formats
	"""
	return set(chain.from_iterable(conversion_methods.values()))

def find_target_format_file(
	file: str,
	formats: List[str]
) -> Union[FileConverter, None]:
	"""Get a FileConverter class based on source format and desired formats.

	Args:
		file (str): The file to get the converter for.
		formats (List[str]): The formats to convert to, in order of preference.

	Returns:
		Union[FileConverter, None]: The converter class that is possible
		and most prefered.
			In case of no possible conversion, `None` is returned.
	"""
	source_format = splitext(file)[1].lstrip('.').lower()

	if not source_format in conversion_methods:
		return

	if (
		source_format in ('rar', 'cbr')
		and not platform in rar_executables
	):
		return

	available_formats = conversion_methods[source_format]

	for format in formats:
		if format in available_formats:
			return available_formats[format]

	return

def convert_file(file: str, formats: List[str]) -> str:
	"""Convert a file from one format to another.

	Args:
		file (str): The file to convert.
		formats (List[str]): A list of formats to convert the file to.
			Order of list is preference of format (left to right).
			
			Should be key `conversion.conversion_methods` -> source_format dict.

	Returns:
		str: The path of the converted file.
	"""
	conversion_class = find_target_format_file(
		file,
		formats
	)
	if conversion_class is not None:
		return conversion_class().convert(file)
	else:
		return file

def __get_format_pref_and_files(
	volume_id: int,
	issue_id: Union[int, None] = None
) -> List[str]:
	"""Get the format preference and load the targeted files into the cursor.

	Args:
		volume_id (int): The ID of the volume to get the files for.

		issue_id (Union[int, None], optional): The ID of the issue to get
		the files for.
			Defaults to None.

	Returns:
		List[str]: The format preference in the settings
	"""
	cursor = get_db()
	
	format_preference = cursor.execute(
		"SELECT value FROM config WHERE key = 'format_preference' LIMIT 1;"
	).fetchone()[0].split(',')
	if format_preference == ['']:
		format_preference = []
	
	if not issue_id:
		cursor.execute("""
			SELECT DISTINCT filepath
			FROM files f
			INNER JOIN issues_files if
			INNER JOIN issues i
			ON
				f.id = if.file_id
				AND if.issue_id = i.id
			WHERE volume_id = ?
			ORDER BY filepath;
			""",
			(volume_id,)
		)

	else:
		cursor.execute("""
			SELECT DISTINCT filepath
			FROM files f
			INNER JOIN issues_files if
			INNER JOIN issues i
			ON
				f.id = if.file_id
				AND if.issue_id = i.id
			WHERE
				volume_id = ?
				AND i.id = ?
			ORDER BY filepath;
			""",
			(volume_id, issue_id)
		)

	return format_preference

def preview_mass_convert(
	volume_id: int,
	issue_id: int = None
) -> List[Dict[str, str]]:
	"""Get a list of suggested conversions for a volume or issue

	Args:
		volume_id (int): The ID of the volume to check for.
		issue_id (int, optional): The ID of the issue to check for.
			Defaults to None.

	Returns:
		List[Dict[str, str]]: The list of suggestions.
			Dicts have the keys `before` and `after`.
	"""	
	cursor = get_db()
	format_preference = __get_format_pref_and_files(
		volume_id,
		issue_id
	)

	result = []
	for (f,) in cursor:
		converter = find_target_format_file(
			f,
			format_preference
		)
		if converter is not None:
			if converter.target_format == 'folder':
				result.append({
					'before': f,
					'after': dirname(f)
				})
			else:
				result.append({
					'before': f,
					'after': splitext(f)[0] + '.' + converter.target_format
				})
	return result

def mass_convert(
	volume_id: int,
	issue_id: Union[int, None] = None,
	files: List[str]= []
) -> None:
	"""Convert files for a volume or issue.

	Args:
		volume_id (int): The ID of the volume to convert for.

		issue_id (Union[int, None], optional): The ID of the issue to convert for.
			Defaults to None.

		files (List[str], optional): Only convert files mentioned in this list.
			Defaults to [].
	"""	
	# We're checking a lot if strings are in this list,
	# so making it a set will increase performance (due to hashing).
	files = set(files)

	cursor = get_db()
	format_preference = __get_format_pref_and_files(
		volume_id,
		issue_id
	)
	
	for (f,) in cursor.fetchall():
		if files and f not in files:
			continue
		
		converter = find_target_format_file(
			f,
			format_preference
		)
		if converter is not None:
			converter().convert(f)

	scan_files(Volume(volume_id).get_info())

	return
