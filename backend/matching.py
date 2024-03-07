#-*- coding: utf-8 -*-

"""
All matching is done here. Can be between file and database,
file and CV result, issue/volume and GC result, etc.
"""

from __future__ import annotations

import logging
from re import compile
from typing import TYPE_CHECKING, Dict, List, Tuple, Union

from backend.blocklist import blocklist_contains
from backend.db import get_db
from backend.enums import SpecialVersion
from backend.helpers import (FilenameData, SearchResultData, SearchResultMatchData, create_range, extract_year_from_date,
                             get_first_of_range)

if TYPE_CHECKING:
	from backend.volumes import VolumeData

clean_title_regex = compile(r'((?<=annual)s|/|\-|\+|,|\!|:|\bthe\s|\band\b|&|’|\'|\"|\bone-shot\b|\btpb\b)')
clean_title_regex_2 = compile(r'\s')

def _match_title(title1: str, title2: str) -> bool:
	"""Determine if two titles match; if they refer to the same thing.

	Args:
		title1 (str): The first title.
		title2 (str): The second title, to which the first title should be compared.

	Returns:
		bool: `True` if the titles match, otherwise `False`.
	"""
	clean_reference_title = clean_title_regex_2.sub(
		'',
		clean_title_regex.sub(
			'',
			title1.lower()
		)
	)

	clean_title = clean_title_regex_2.sub(
		'',
		clean_title_regex.sub(
			'',
			title2.lower()
		)
	)

	result = clean_reference_title == clean_title
	logging.debug(f'Matching titles ({title1} -> {clean_reference_title}, {title2} -> {clean_title}): {result}')
	return result


def _match_year(
	reference_year: Union[None, int],
	check_year: Union[None, int],
	end_year: Union[None, int] = None,
	conservative: bool = False
) -> bool:
	"""Check if two years match, with one year of 'wiggle room'.

	Args:
		reference_year (Union[None, int]): The year to check against.

		check_year (Union[None, int]): The year to check.

		end_year (Union[None, int], optional): A different year as the end border.
		Supply `None` to disable and use reference_year for both borders instead.
			Defaults to None.

		conservative (bool, optional): If either of the years is `None`,
		play it safe and return `True`.
			Defaults to False.

	Returns:
		bool: `True` if the years 'match', otherwise `False`.
	"""
	if None in (reference_year, check_year):
		return conservative

	end_border = end_year or reference_year

	return reference_year - 1 <= check_year <= end_border + 1


def _match_volume_number(
	volume_id: int,
	check_number: Union[None, int, Tuple[int, int]],
	conservative: bool = False
) -> bool:
	"""Check if the volume number matches the one of the volume or it's year.
	If volume is 'volume-as-issue', then the volume number (or range) should 
	match to an issue number in the volume.

	Args:
		volume_id (int): The ID of the volume that the volume numbers are for.

		check_number (Union[None, int, Tuple[int, int]]): The volume number
		(or range) to check.

		conservative (bool, optional): If either of the volume numbers is `None`,
		play it safe and return `True`.
			Defaults to False.

	Returns:
		bool: `True` if the volume numbers 'match', otherwise `False`.
	"""
	cursor = get_db(dict)
	cursor.execute("""
		SELECT volume_number, special_version, year
		FROM volumes
		WHERE id = ?
		LIMIT 1;
		""",
		(volume_id,)
	)
	volume_number, special_version, year = cursor.fetchone()

	if (volume_number, year) == (None, None):
		return conservative

	if check_number is None:
		return conservative

	if isinstance(check_number, int):
		if check_number == volume_number:
			return True

		if _match_year(year, check_number):
			return True

	# Volume numbers don't match, but
	# it's possible that the volume is volume-as-issue.
	# Then the volume number is actually the issue number.
	# So check if an issue exists with the volume number.

	if special_version != SpecialVersion.VOLUME_AS_ISSUE:
		return False

	if isinstance(check_number, tuple):
		cursor.execute("""
			SELECT 1
			FROM issues
			WHERE volume_id = ?
				AND (calculated_issue_number = ?
					OR calculated_issue_number = ?)
			LIMIT 2;
			""",
			(volume_id, *check_number)
		)

		return len(cursor.fetchall()) == 2
		
	else:
		cursor.execute("""
			SELECT 1
			FROM issues
			WHERE volume_id = ?
				AND calculated_issue_number = ?
			LIMIT 1;
			""",
			(volume_id, check_number)
		)
	
		return cursor.fetchone() is not None


def _match_special_version(
	reference_version: Union[SpecialVersion, str, None],
	check_version: Union[SpecialVersion, str, None],
	issue_number: Union[None, float, Tuple[float, float]] = None
) -> bool:
	"""Check if special version states match. Takes into consideration that
	files have lacking state specificity.

	Args:
		reference_version (Union[SpecialVersion, str, None]):
		The state to check against.

		check_version (Union[SpecialVersion, str, None]):
		The state to check.

		issue_number (Union[None, float, Tuple[float, float]], optional):
		The issue number to check for if applicable.
		So that issue_number == 1 and special_version == 'one-shot' | 'hard-cover'
		will match.	
			Defaults to None.

	Returns:
		bool: `True` if the states 'match', otherwise `False`.
	"""
	if reference_version == check_version:
		return True

	if issue_number == 1.0 and reference_version in (
		SpecialVersion.HARD_COVER,
		SpecialVersion.ONE_SHOT
	):
		return True

	if (reference_version == SpecialVersion.VOLUME_AS_ISSUE
		and check_version == SpecialVersion.NORMAL):
		return True

	# Volume could be specific special version that
	# extract_filename_data can't pick up
	# and that that is the reason there is a mismatch
	return (
		check_version == SpecialVersion.TPB
		and reference_version in (
			SpecialVersion.HARD_COVER,
			SpecialVersion.ONE_SHOT,
			SpecialVersion.VOLUME_AS_ISSUE
		)
	)


def folder_extraction_filter(
	file_data: FilenameData,
	volume_data: VolumeData,
	end_year: Union[int, None]
) -> bool:
	"""The filter applied to the files when extracting from a folder,
	which decides which file is relevant and which one isn't.
	This filter is relatively conservative.

	Args:
		file_data (FilenameData): The output of `backend.files.extract_filename_data()`
		for the file.
		volume_data (VolumeData): The info about the volume.
		end_year (Union[int, None]): Year of last issue or volume year.

	Returns:
		bool: Whether or not the file passes the filter
		(if it should be kept or not).
	"""
	annual = 'annual' in volume_data.title.lower()
	return (
		_match_title(file_data['series'], volume_data.title)
		and file_data['annual'] == annual
		and (
			_match_year(
				volume_data.year,
				file_data['year'],
				end_year
			)
			or _match_volume_number(
				volume_data.id,
				file_data['volume_number'],
			)
			# Or neither should be found (we play it safe so we keep those)
			or (file_data['year'], file_data['volume_number']) == (None, None)
		)
	)


def file_importing_filter(
	file_data: FilenameData,
	volume_data: VolumeData,
	volume_issues: List[dict]
) -> bool:
	"""Filter for matching files to volumes.

	Args:
		file_data (FilenameData): The output of files.extract_filename_data() for the file.
		volume_data (VolumeData): The data of the volume.
		volume_issues (List[dict]): The issues of the volume.

	Returns:
		bool: Whether or not the file has passed the filter.
	"""
	# Note: value of key could be None
	# 		if issue doesn't have release date.
	issue_number_to_year: Dict[float, Union[int, None]] = {
		issue['calculated_issue_number']:
			extract_year_from_date(issue['date'])
		for issue in volume_issues
	}

	matching_special_version = _match_special_version(
		volume_data.special_version,
		file_data['special_version'],
		file_data['issue_number']
	)

	matching_year = _match_year(
		volume_data.year,
		file_data['year'],
		issue_number_to_year.get(
			get_first_of_range(
				file_data['volume_number']
				if volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE else
				file_data['issue_number']
			)
		)
	)

	matching_volume_number = _match_volume_number(
		volume_data.id,
		file_data['volume_number']
	)

	is_match = (
		matching_special_version
		and (
			matching_volume_number
			or
			matching_year
		)
	)
	
	return is_match


def GC_group_filter(
	processed_desc: FilenameData,
	volume_id: int,
	volume_title: str,
	volume_year: int,
	last_issue_date: str,
	special_version: SpecialVersion
) -> bool:
	"""A filter for deciding if a GC download group is a match for the 
	volume/issue.

	Args:
		processed_desc (FilenameData): Output of files.extract_filename_data() for 
		group title.
		volume_id (int): The ID of the volume.
		volume_title (str): The title of the volume.
		volume_year (int): The year of the volume.
		last_issue_date (str): The date of the last released issue of the volume.
		special_version (SpecialVersion): The special version state of the volume.

	Returns:
		bool: Whether or not the group passes the filter.
	"""
	last_year = extract_year_from_date(last_issue_date, volume_year)
	annual = 'annual' in volume_title.lower()

	matching_title = _match_title(
		volume_title,
		processed_desc['series']
	)

	matching_volume_number = _match_volume_number(
		volume_id,
		processed_desc['volume_number'],
		conservative=True
	)
	
	matching_year = _match_year(
		volume_year,
		processed_desc['year'],
		last_year,
		conservative=True
	)
	
	matching_special_version = _match_special_version(
		special_version.value,
		processed_desc['special_version'],
		processed_desc['issue_number']
	)
	
	is_match = (
		matching_title
		and matching_volume_number
		and matching_year
		and matching_special_version
		and processed_desc['annual'] == annual
	)
	
	return is_match


def check_search_result_match(
	result: SearchResultData,
	volume_id: int,
	title: str,
	special_version: SpecialVersion,
	issue_numbers: Dict[float, int],
	calculated_issue_number: float=None,
	year: int=None
) -> SearchResultMatchData:
	"""Determine if a result is a match with what is searched for

	Args:
		result (SearchResultData): A result in SearchSources.search_all()

		title (str): Title of volume

		volume_number (int): The volume number of the volume

		special_version (SpecialVersion): What type of special version the volume is.

		issue_numbers (Dict[float, int]): calculated_issue_number to release year
		for all issues of volume

		calculated_issue_number (float, optional): The calculated issue number of
		the issue.
			Output of `files.process_issue_number()`.

			Defaults to None.

		year (int, optional): The year of the volume.
			Defaults to None.

	Returns:
		SearchResultMatchData: A dict with the key `match` having a bool value for if it matches or not and
		the key `match_issue` with the reason for why it isn't a match
		if that's the case (otherwise `None`).
	"""
	annual = 'annual' in title.lower()

	if blocklist_contains(result['link']):
		return {'match': False, 'match_issue': 'Link is blocklisted'}

	if result['annual'] != annual:
		return {'match': False, 'match_issue': 'Annual conflict'}

	if not _match_title(title, result['series']):
		return {'match': False, 'match_issue': 'Titles don\'t match'}

	if not _match_volume_number(
		volume_id,
		result['volume_number'],
		conservative=True
	):
		return {'match': False, 'match_issue': 'Volume numbers don\'t match'}

	if not _match_special_version(
		special_version,
		result['special_version'],
		result['issue_number']
	):
		return {'match': False, 'match_issue': 'Special version conflict'}

	if special_version in (SpecialVersion.NORMAL, SpecialVersion.VOLUME_AS_ISSUE):
		if result['issue_number'] is not None:
			issue_key = 'issue_number'
		else:
			issue_key = 'volume_number'
		
		issue_number_is_equal = (
			(
				# Search result for volume
				calculated_issue_number is None
				and
				all(i in issue_numbers for i in create_range(result[issue_key]))
			)
			or
			(
				# Search result for issue
				calculated_issue_number is not None
				# Issue number equals issue that is searched for
				and isinstance(result[issue_key], float)
				and result[issue_key] == calculated_issue_number
			)
		)
		if not issue_number_is_equal:
			return {'match': False, 'match_issue': 'Issue numbers don\'t match'}

	if not _match_year(
		year,
		result['year'],
		issue_numbers.get(
			get_first_of_range(
				result['volume_number']
				if special_version == SpecialVersion.VOLUME_AS_ISSUE else
				result['issue_number']
			)
		),
		conservative=True
	):
		return {'match': False, 'match_issue': 'Year doesn\'t match'}

	return {'match': True, 'match_issue': None}
