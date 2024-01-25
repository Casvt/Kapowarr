#-*- coding: utf-8 -*-

"""
Converting files to a different format
"""

from itertools import chain
from multiprocessing import cpu_count
from multiprocessing.pool import Pool
from os.path import dirname, splitext
from sys import platform
from typing import Dict, List, Set, Tuple, Union

from backend.converters import FileConverter, rar_executables
from backend.enums import SpecialVersion
from backend.file_extraction import extract_filename_data
from backend.settings import Settings
from backend.volumes import Volume, scan_files

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
		if source_format == format:
			break

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
		return conversion_class.convert(file)
	else:
		return file

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
	settings = Settings()
	volume = Volume(volume_id)
	
	format_preference = settings['format_preference']
	extract_issue_ranges = settings['extract_issue_ranges']
	special_version = volume['special_version']
	volume_as_issue = special_version == SpecialVersion.VOLUME_AS_ISSUE

	result = []
	for f in sorted(volume.get_files(issue_id)):
		converter = None

		if (extract_issue_ranges
		and ((
				not volume_as_issue
				and isinstance(extract_filename_data(f)['issue_number'], tuple)
			)
			or (
				volume_as_issue
				and isinstance(extract_filename_data(f)['volume_number'], tuple)
			)
		)):
			converter = find_target_format_file(
				f,
				['folder']
			)

		if converter is None:
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
	files: List[str] = []
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

	settings = Settings()
	volume = Volume(volume_id)
	
	format_preference = settings['format_preference']
	extract_issue_ranges = settings['extract_issue_ranges']
	special_version = volume['special_version']
	volume_as_issue = special_version == SpecialVersion.VOLUME_AS_ISSUE

	planned_conversions: List[Tuple[str, List[str]]] = []
	for f in volume.get_files(issue_id):
		if files and f not in files:
			continue

		converted = False
		if (extract_issue_ranges
		and ((
				not volume_as_issue
				and isinstance(extract_filename_data(f)['issue_number'], tuple)
			)
			or (
				volume_as_issue
				and isinstance(extract_filename_data(f)['volume_number'], tuple)
			)
		)):
			converter = find_target_format_file(
				f,
				['folder']
			)
			if converter is not None:
				resulting_files = converter.convert(f)
				for file in resulting_files:
					planned_conversions.append(
						(file, format_preference)
					)
				converted = True

		if not converted:
			planned_conversions.append(
				(f, format_preference)
			)

	# Don't start more processes than files, but also not
	# more than that is supported by the CPU
	processes = min(len(planned_conversions), cpu_count())
	
	if processes == 0:
		return
	
	elif processes == 1:
		# Avoid mp overhead when we're only converting one file
		convert_file(
			*planned_conversions[0]
		)
	
	else:
		with Pool(processes=processes) as pool:
			pool.starmap(
				convert_file,
				planned_conversions,
				chunksize=10
			)

	scan_files(volume_id)

	return
