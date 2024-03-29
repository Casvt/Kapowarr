#-*- coding: utf-8 -*-

"""
Extracting data from filenames or search results and generalising it.

extract_filename_data() is inspired by the file parsing of Kavita and Comictagger:
	https://github.com/Kareadita/Kavita/blob/develop/API/Services/Tasks/Scanner/Parser/Parser.cs
	https://github.com/comictagger/comictagger/blob/develop/comicapi/filenameparser.py
"""

import logging
from os.path import basename, dirname, splitext
from re import IGNORECASE, compile
from typing import Tuple, Union

from backend.enums import SpecialVersion
from backend.helpers import FilenameData
from backend.helpers import fix_year as fix_broken_year
from backend.helpers import normalize_string

cover = 'cover'
alphabet = 'abcdefghijklmnopqrstuvwxyz'
alphabet = {letter: str(alphabet.index(letter) + 1).zfill(2) for letter in alphabet}
digits = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
image_extensions = ('.png','.jpeg','.jpg','.webp','.gif',
					'.PNG','.JPEG','.JPG','.WEBP','.GIF')
supported_extensions = image_extensions + ('.cbz','.zip','.rar','.cbr','.tar.gz','.7zip','.7z','.cb7','.cbt','.epub','.pdf')
file_extensions = r'\.(' + '|'.join(e[1:] for e in supported_extensions) + r')$'
volume_regex_snippet = r'\b(?:v(?:ol|olume)?)(?:\.\s|[\.\-\s])?(\d+(?:\s?\-\s?\d+)?|(?<!v)I{1,3})'
year_regex_snippet = r'(?:(\d{4})(?:-\d{2}){0,2}|(\d{4})[\s\.]?-(?:[\s\.]?\d{4})?|(?:\d{2}-){1,2}(\d{4})|(\d{4})[\s\.\-]Edition|(\d{4})\-\d{4}\s{3}\d{4})'
issue_regex_snippet = r'(?!\d+(?:th|rd|st|\s?(?:gb|mb)))(?<!\')(?:\d+(?:\.\d{1,2}|\.?\w{1,3}|[\s\-\.]?[½¼])?|[½¼])'

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
special_version_regex = compile(r'(?:\b|\()(?:(?P<tpb>tpb|trade paper back)|(?P<one_shot>os|one[\- ]?shot)|(?P<hard_cover>hc|hard[\- ]?cover))(?:\b|\))', IGNORECASE)
volume_regex = compile(volume_regex_snippet, IGNORECASE)
volume_folder_regex = compile(volume_regex_snippet + r'|^(\d+)$', IGNORECASE)
issue_regex = compile(r'\( (\-?' + issue_regex_snippet + r')\)', IGNORECASE)
issue_regex_2 = compile(r'(?<!\()(?:c|issues?)(?:[\s\-\.]?|\s\-\s)(?:#\s*)?(\-?' + issue_regex_snippet + r'(?:[\s\.]?\-[\s\.]?\-?' + issue_regex_snippet + r')?)\b(?!\))', IGNORECASE)
issue_regex_3 = compile(r'(' + issue_regex_snippet + r')[\s\-\.]?\(?[\s\-\.]?of[\s\-\.]?' + issue_regex_snippet + r'\)?', IGNORECASE)
issue_regex_4 = compile(r'(?<!--)(?:#\s*)?(\-?' + issue_regex_snippet + r'[\s\.]?-[\s\.]?' + issue_regex_snippet + r')\b(?!--)', IGNORECASE)
issue_regex_5 = compile(r'#\s*(\-?' + issue_regex_snippet + r')\b(?![\s\.]?\-[\s\.]?' + issue_regex_snippet + r')', IGNORECASE)
issue_regex_6 = compile(r'(?:(?P<i_start>^)|(?<=(?<!part)(?:\s|\-)))(?P<n_c>n)?(\-?' + issue_regex_snippet + r')(?=(?(n_c)c\d+|(?(i_start)\s\-|))(?:\s|\-|$))', IGNORECASE)
issue_regex_7 = compile(r'^(\-?' + issue_regex_snippet + r')$', IGNORECASE)
year_regex = compile(r'\((?:\w+\s)?' + year_regex_snippet + r'\)|--' + year_regex_snippet + r'--|, ' + year_regex_snippet + r'\s{3}|\b(?:(?:\d{2}-){1,2}(\d{4})|(\d{4})(?:-\d{2}){1,2})\b', IGNORECASE)
series_regex = compile(r'(^(\d+\.)?\s+|^\d+\s{3}|\s(?=\s)|[\s,]+$)')
annual_regex = compile(r'\+[\s\.]?annuals?|annuals?[\s\.]?\+|^((?!annuals?).)*$', IGNORECASE)
cover_regex = compile(r'\b(?<!no[ \-])(?<!hard[ \-])(?<!\d[ \-]covers)cover\b|n\d+c(\d+)|(?:\b|\d)i?fc\b', IGNORECASE)

def _calc_float_issue_number(issue_number: str) -> Union[float, None]:
	"""Convert an issue number from string to representive float

	Args:
		issue_number (str): The issue number to convert

	Returns:
		Union[float, None]: Either the float version or `None` on fail.
	"""
	try:
		# Number is already a valid float, just in string form.
		return float(issue_number)
	except ValueError:
		pass

	# Issue has special number notation
	issue_number = (issue_number
		.replace(',','.')
		.replace('?','0')
		.rstrip('.')
		.lower()
	)
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

			elif c == '¼':
				converted_issue_number += '3'

			elif c in alphabet:
				converted_issue_number += alphabet.get(c, alphabet['z'])

	if converted_issue_number:
		return float(converted_issue_number)
	return

def process_issue_number(
	issue_number: str
) -> Union[float, Tuple[float, float], None]:
	"""Convert an issue number or issue range to a (tuple of) float.

	Args:
		issue_number (str): The issue number.

	Returns:
		Union[float, Tuple[float, float], None]: Either a
		float representing the issue number,
		a tuple of floats representing the issue numbers when
		the original issue number was a range of numbers (e.g. 1a-5b)
		or `None` if it wasn't succesfull in converting.
	"""
	if '-' in issue_number[1:]:
		entries = issue_number[1:].replace(' ', '').split('-', 1)
		entries[0] = issue_number[0] + entries[0]

		if not all(
			e[0] in digits or (
				e[0] == '-'
				and e[1] in digits
			)
			for e in entries
		):
			return _calc_float_issue_number(issue_number)

		start = _calc_float_issue_number(entries[0])
		end = _calc_float_issue_number(entries[1])

		if start is None:
			if end is None:
				return None
			else:
				return end
		elif end is None:
			return start
		else:
			return (start, end)

	return _calc_float_issue_number(issue_number)

def convert_volume_number_to_int(
	volume_number: Union[str, None]
) -> Union[int, Tuple[int, int], None]:
	"""Convert the volume number (or volume range) from float(s) to int(s).

	Args:
		volume_number (Union[str, None]): The volume number (range) in string format

	Returns:
		Union[int, Tuple[int, int], None]: The converted volume number(s).
	"""
	if volume_number is None:
		return

	if 'i' in volume_number.lower():
		i_count = volume_number.lower().count('i')
		if i_count == len(volume_number):
			volume_number = str(i_count)

	result = process_issue_number(volume_number)
	if isinstance(result, float):
		result = int(result)
	elif isinstance(result, tuple):
		result = int(result[0]), int(result[1])
	return result

def extract_filename_data(
	filepath: str,
	assume_volume_number: bool = True,
	prefer_folder_year: bool = False,
	fix_year: bool = False
) -> FilenameData:
	"""Extract comic data from string and present in a formatted way.

	Args:
		filepath (str): The source string (like a filepath, filename or GC title).

		assume_volume_number (bool, optional): If no volume number was found,
		should `1` be assumed? When a series has only one volume,
		often the volume number isn't included in the filename.
			Defaults to True.

		prefer_folder_year (bool, optional): Use year in foldername instead of
		year in filename, if available.
			Defaults to False.

		fix_year (bool, optional): If the extracted year is most likely broken,
		fix it. See `helpers.fix_year()`.
			Defaults to False.

	Returns:
		FilenameData: The extracted data in a formatted way
	"""
	logging.debug(f'Extracting filename data: {filepath}')
	series, year, volume_number, special_version, issue_number = (
		None, None, None, None, None
	)

	# Determine annual or not
	annual_result = annual_regex.search(basename(filepath))
	annual_folder_result = annual_regex.search(basename(dirname(filepath)))
	annual = not (annual_result and annual_folder_result)

	# Generalise filename
	filepath = (normalize_string(filepath)
		.replace('+',' ')
		.replace('_','-')
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

	is_image_file = filepath.endswith(image_extensions)

	# Only keep filename
	filename = basename(filepath)
	if splitext(filename)[1].lower() in supported_extensions:
		filename = splitext(filename)[0]

	# Keep stripped version of filename without (), {}, [] and extensions
	clean_filename = strip_filename_regex.sub(
		lambda m: " " * len(m.group()), filename
	)
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
	all_year_pos, all_year_folderpos = [(10_000, 10_000)], [(10_000, 10_000)]

	if prefer_folder_year:
		year_order = (foldername, filename, upper_foldername)
	else:
		year_order = (filename, foldername, upper_foldername)

	for location in year_order:
		year_result = list(year_regex.finditer(location))
		if year_result:
			if year is None:
				year = next(y for y in year_result[0].groups() if y)
			if location == filename:
				all_year_pos = [(r.start(0), r.end(0)) for r in year_result]
			if location == foldername:
				all_year_folderpos = [(r.start(0), r.end(0)) for r in year_result]

	# Get volume number
	volume_end, volume_pos, volume_folderpos, volume_folderend = (
		0, 10_000, 10_000, 0
	)
	volume_result = volume_regex.search(clean_filename)
	if volume_result:
		# Volume number found (e.g. Series Volume 1 Issue 6.ext)
		volume_number = convert_volume_number_to_int(volume_result.group(1))
		volume_pos = volume_result.start(0)
		volume_end = volume_result.end(1)

	# Find volume match in folder for finding series name
	# (or when volume number couldn't be found in filename)
	volume_folder_result = volume_folder_regex.search(foldername)
	if volume_folder_result:
		# Volume number found in folder (e.g. Series Volume 1/Issue 5.ext)
		volume_folderpos = volume_folder_result.start(0)
		volume_folderend = volume_folder_result.end(0)
		if not volume_result:
			volume_number = convert_volume_number_to_int(
				volume_folder_result.group(1) or volume_folder_result.group(2)
			)

	if not volume_result and not volume_folder_result and assume_volume_number:
		volume_number = 1

	# Check if it's a special version
	issue_pos, issue_folderpos = 10_000, 10_000
	special_pos, special_end = 10_000, 0
	special_result = special_version_regex.search(filename)
	cover_result = cover_regex.search(filename)
	if cover_result:
		special_version = cover
		if cover_result.group(1):
			special_pos = cover_result.start(1)
			special_end = cover_result.end(1)
		else:
			special_pos = cover_result.start(0)
			special_end = cover_result.end(0)

	elif special_result:
		special_version = [
			k for k, v in special_result.groupdict().items()
			if v is not None
		][0].replace('_', '-')
		special_pos = special_result.start(0)

	if special_version in (None, cover):
		# No special version so find issue number
		if not is_image_file:
			pos_options = (
				(filename,
					{'pos': volume_end},
					(issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
						issue_regex_5, issue_regex_6)),
				(filename,
					{'endpos': volume_pos},
					(issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
	  					issue_regex_5))
			)
		else:
			pos_options = (
				(foldername,
					{'pos': volume_folderend},
					(issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
	  					issue_regex_5, issue_regex_6)),
				(foldername,
					{'endpos': volume_folderpos},
					(issue_regex, issue_regex_2, issue_regex_3, issue_regex_4,
						issue_regex_5))
			)

		for file_part_with_issue, pos_option, regex_list in pos_options:
			for regex in regex_list:
				r = list(regex.finditer(file_part_with_issue, **pos_option))
				group_number = 1 if regex != issue_regex_6 else 3
				if r:
					r.sort(key=lambda e: (
						int(e.group(group_number)[-1] not in '0123456789'),
						(
							1 / e.start(0)
							if e.start(0) else
							0
						)
					))

					for result in r:
						if (
							file_part_with_issue == filename
							and not any(
								start_pos <= result.start(0) < end_pos
								or start_pos < result.end(0) <= end_pos
								for start_pos, end_pos in all_year_pos
							)
							and (
								not special_version
								or not (
									special_pos <= result.start(0) < special_end
									or special_pos < result.end(0) <= special_end
								)
							)
							or
							file_part_with_issue == foldername
							and not any(
								start_pos <= result.start(0) < end_pos
								or start_pos < result.end(0) <= end_pos
								for start_pos, end_pos in all_year_folderpos
							)
						):
							issue_number = result.group(group_number)
							if not is_image_file:
								issue_pos = result.start(0)
							else:
								issue_folderpos = result.start(0)
							break
					else:
						continue
					break
			else:
				continue
			break

		else:
			if not is_image_file:
				issue_result = issue_regex_7.search(no_ext_clean_filename)
				if issue_result:
					# Issue number found. File starts with issue number
					# (e.g. Series/Volume N/{issue_number}.ext)
					issue_number = issue_result.group(1)
					issue_pos = issue_result.start(0)

	if not issue_number and not special_version:
		special_version = SpecialVersion.TPB.value

	# Get series
	series_pos = min(
		all_year_pos[0][0],
		volume_pos,
		special_pos,
		issue_pos
	)
	if series_pos and not is_image_file:
		# Series name is assumed to be in the filename,
		# left of all other information
		series = no_ext_clean_filename[:series_pos - 1]
	else:
		series_folder_pos = min(
			all_year_folderpos[0][0], volume_folderpos, issue_folderpos
		)
		if series_folder_pos:
			# Series name is assumed to be in the foldername,
			# left of all other information
			series = foldername[:series_folder_pos - 1]
		else:
			# Series name is assumed to be the upper foldername
			series = strip_filename_regex.sub('', upper_foldername)
	series = series_regex.sub('', series.replace('-', ' '))

	# Format output
	if issue_number is not None:
		calculated_issue_number = process_issue_number(issue_number)
	else:
		calculated_issue_number = None

	year = int(year) if year else None
	if fix_year and year is not None:
		year = fix_broken_year(year)

	file_data = FilenameData({
		'series': series,
		'year': year,
		'volume_number': volume_number,
		'special_version': special_version,
		'issue_number': calculated_issue_number,
		'annual': annual
	})

	logging.debug(f'Extracting filename data: {file_data}')

	return file_data

