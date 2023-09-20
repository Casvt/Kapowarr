#-*- coding: utf-8 -*-

"""This file contains functions regarding searching for a volume or issue with getcomics.org as the source
"""

import logging
from asyncio import create_task, gather, run
from re import compile
from typing import Dict, List, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from requests import get

from backend.blocklist import blocklist_contains
from backend.db import get_db
from backend.files import extract_filename_data
from backend.settings import private_settings

clean_title_regex = compile(r'((?<=annual)s|(?!\s)\-(?!\s)|\+|,|\!|:|\bthe\s|\band\b|&|’|\'|\"|\bone-shot\b|\btpb\b)')
clean_title_regex_2 = compile(r'(\s-\s|\s+|/)')

def _check_matching_titles(title1: str, title2: str) -> bool:
	"""Determine if two titles match; if they refer to the same thing.

	Args:
		title1 (str): The first title.
		title2 (str): The second title, to which the first title should be compared.

	Returns:
		bool: `True` if the titles match, otherwise `False`.
	"""
	pre_clean_title = clean_title_regex.sub('', title1.lower())
	clean_reference_title = (clean_title_regex_2
		.sub(' ', pre_clean_title)
		.strip())

	pre_clean_title = clean_title_regex.sub('', title2.lower())
	clean_title = (clean_title_regex_2
		.sub(' ', pre_clean_title)
		.strip())

	result = clean_reference_title == clean_title
	logging.debug(f'Matching titles ({title1} -> {clean_reference_title}, {title2} -> {clean_title}): {result}')
	return result

def _check_match(
	result: dict,
	title: str,
	volume_number: int,
	special_version: Union[str, None],
	issue_numbers: Dict[float, int],
	calculated_issue_number: float=None,
	year: int=None
) -> dict:
	"""Determine if a result is a match with what is searched for

	Args:
		result (dict): A result in SearchSources.search_results
		title (str): Title of volume
		volume_number (int): The volume number of the volume
		special_version (str): What type of special version the volume is, or None
		issue_numbers (Dict[float, int]): calculated_issue_number to release year for all issues of volume
		calculated_issue_number (float, optional): The calculated issue number of the issue 
		(output of files.process_issue_number()). Defaults to None.
		year (int, optional): The year of the volume. Defaults to None.

	Returns:
		dict: A dict with the key `match` having a bool value for if it matches or not and
		the key `match_issue` with the reason for why it isn't a match if that's the case (otherwise `None`).
	"""
	annual = 'annual' in title.lower()

	if blocklist_contains(result['link']):
		return {'match': False, 'match_issue': 'Link is blocklisted'}

	if result['annual'] != annual:
		return {'match': False, 'match_issue': 'Annual conflict'}

	if not _check_matching_titles(title, result['series']):
		return {'match': False, 'match_issue': 'Title doesn\'t match'}

	if result['volume_number'] != volume_number and (result['volume_number'] is not None or year is None):
		return {'match': False, 'match_issue': 'Volume number doesn\'t match'}

	if special_version != result['special_version'] and not (
		special_version == 'hard-cover'
		and result['special_version'] == 'tpb'
	):
		return {'match': False, 'match_issue': 'Special version conflict'}

	if not special_version:
		issue_number_is_equal = (
			(
				# Search result for volume
				calculated_issue_number is None
				and
				(
					# Issue number is in volume
					(isinstance(result['issue_number'], float) and result['issue_number'] in issue_numbers)
					# Issue range's start and end are both in volume
					or (isinstance(result['issue_number'], tuple) and all(i in issue_numbers for i in result['issue_number']))
				)
			)
			or
			(
				# Search result for issue
				calculated_issue_number is not None
				# Issue number equals issue that is searched for
				and isinstance(result['issue_number'], float)
				and result['issue_number'] == calculated_issue_number
			)
		)
		if not issue_number_is_equal:
			return {'match': False, 'match_issue': 'Issue number(s) don\'t match'}
	
	year_is_equal = (
		year is None
		or result['year'] is None
		or (
			year - 1 <= result['year'] <= year + 1 # Year in volume release year
			# Year in issue release year
			or (isinstance(result['issue_number'], float) and issue_numbers.get(result['issue_number']) == result['year']) 
			or (isinstance(result['issue_number'], tuple) and issue_numbers.get(result['issue_number'][0]) == result['year'])
		)
	)
	if not year_is_equal:
		return {'match': False, 'match_issue': 'Year doesn\'t match'}
		
	return {'match': True, 'match_issue': None}

def _sort_search_results(
	result: dict,
	title: str,
	volume_number: int,
	year: int=None,
	calculated_issue_number: float=None
) -> List[int]:
	"""Sort the search results

	Args:
		result (dict): A result in from `search.SearchSources.search_all`.
		title (str): Title of volume
		volume_number (int): The volume number of the volume
		year (int, optional): The year of the volume. Defaults to None.
		calculated_issue_number (float, optional): The calculated_issue_number of the issue. Defaults to None.

	Returns:
		List[int]: A list of numbers which determines the ranking of the result.
	"""
	rating = []

	# Prefer matches
	rating.append(int(not result['match']))

	# The more words in the search term that are present in the search results' title, 
	# the higher ranked it gets
	split_title = title.split(' ')
	rating.append(len([word for word in result['series'].split(' ') if not word in split_title]))

	# Prefer volume number or year matches, even better if both match
	v_match = int(not (result['volume_number'] is not None and result['volume_number'] == volume_number))
	y_match = int(not (year is not None and result['year'] is not None and year - 1 <= result['year'] <= year + 1))
	rating.append(v_match + y_match)

	# Sort on issue number fitting
	if calculated_issue_number is not None:
		if isinstance(result['issue_number'], float) and calculated_issue_number == result['issue_number']:
			# Issue number is direct match
			rating.append(0)

		elif isinstance(result['issue_number'], tuple):
			if result['issue_number'][0] <= calculated_issue_number <= result['issue_number'][1]:
				# Issue number falls between range
				rating.append(1 - (1 / (result['issue_number'][1] - result['issue_number'][0] + 1)))
			else:
				# Issue number falls outside so release is not usefull
				rating.append(3)

		elif result['issue_number'] is None and result['special_version'] is not None:
			# Issue number not found but is special version
			rating.append(2)

		else:
			rating.append(3)
	else:
		if isinstance(result['issue_number'], tuple):
			rating.append(1.0 / (result['issue_number'][1] - result['issue_number'][0] + 1))

		elif isinstance(result['issue_number'], float):
			rating.append(1)

	return rating

class SearchSources:
	"""For getting search results from various sources
	"""	
	def __init__(self, query: str):
		"""Prepare a search

		Args:
			query (str): The search string to search for in the sources
		"""
		self.query = query
		self.source_list = [
			self._get_comics,
			self._indexers
		]

	def search_all(self) -> List[dict]:
		"""Search all sources for the query.
		"""
		result = []
		for source in self.source_list:
			result += source()
		return result

	async def __fetch_one(
		self,
		session: ClientSession,
		url: str,
		params: dict,
		headers: dict
	):
		async with session.get(url, params=params, headers=headers) as response:
			return await response.text()

	async def __fetch_GC_pages(self, pages: range):
		async with ClientSession() as session:
			tasks = [
				create_task(self.__fetch_one(
					session,
					f'{private_settings["getcomics_url"]}/page/{p}',
					{'s': self.query},
					{'user-agent': 'Kapowarr'}
				)) for p in pages
			]
			responses = await gather(*tasks)
			return [BeautifulSoup(r, 'html.parser') for r in responses]

	def _get_comics(self) -> List[dict]:
		"""Search for the query in getcomics

		Returns:
			List[dict]: The search results
		"""		
		search_results = get(
			private_settings["getcomics_url"],
			params={'s': self.query},
			headers={'user-agent': 'Kapowarr'},
			timeout=30
		).text
		soup = BeautifulSoup(search_results, 'html.parser')
		pages = soup.find_all(['a','span'], {"class": 'page-numbers'})
		pages = min(int(pages[-1].get_text(strip=True)), 10) if pages else 1

		results = []
		parsed_results = run(self.__fetch_GC_pages(range(2, pages + 1)))
		for page in [soup] + parsed_results:
			results += page.find_all('article', {'class': 'post'})

		formatted_results = []
		for result in results:
			link = result.find('a')['href']
			title = result.find("h1", {"class": "post-title"}).get_text(strip=True)

			data = extract_filename_data(title, False)
			data.update({
				'link': link,
				'display_title': title,
				'source': 'GetComics'
			})
			formatted_results.append(data)
		
		return formatted_results
	
	def _indexers(self) -> List[dict]:
		return []

def manual_search(
	volume_id: int,
	issue_id: int=None
) -> List[dict]:
	"""Do a manual search for a volume or issue

	Args:
		volume_id (int): The id of the volume to search for
		issue_id (int, optional): The id of the issue to search for
		(in the case that you want to search for an issue instead of a volume).
		Defaults to None.

	Returns:
		List[dict]: List with search results.
	"""
	cursor = get_db()
	cursor.execute("""
		SELECT
			title,
			volume_number, year,
			special_version
		FROM volumes
		WHERE id = ?
		LIMIT 1;
	""", (volume_id,))
	title, volume_number, year, special_version = cursor.fetchone()
	title: str
	volume_number: int
	year: int
	special_version: Union[str, None]
	issue_number: int = None
	calculated_issue_number: int = None
	if issue_id and not special_version:
		cursor.execute("""
			SELECT
				issue_number, calculated_issue_number
			FROM issues
			WHERE id = ?
			LIMIT 1;
		""", (issue_id,))
		issue_number, calculated_issue_number = cursor.fetchone()
	
	logging.info(
		f'Starting manual search: {title} ({year}) {"#" + issue_number if issue_number else ""}'
	)

	# Prepare query
	title = title.replace(':', '')

	if special_version == 'tpb':
		query_formats = (
			'{title} Vol. {volume_number} ({year}) TPB',
			'{title} ({year}) TPB',
			'{title} Vol. {volume_number} TPB',
			'{title} Vol. {volume_number}',
			'{title}'
		)
	elif issue_number is None:
		query_formats = (
			'{title} Vol. {volume_number} ({year})',
			'{title} ({year})',
			'{title} Vol. {volume_number}',
			'{title}'
		)
	else:
		query_formats = (
			'{title} #{issue_number} ({year})',
			'{title} Vol. {volume_number} #{issue_number}',
			'{title} #{issue_number}',
			'{title}'
		)

	if year is None:
		query_formats = tuple(f.replace('({year})', '') for f in query_formats)

	# Get formatted search results
	results = []
	for format in query_formats:
		search = SearchSources(
			format.format(
				title=title, volume_number=volume_number, year=year, issue_number=issue_number
			)
		)
		results += search.search_all()

	# Remove duplicates 
	# because multiple formats can return the same result
	results: List[dict] = list({r['link']: r for r in results}.values())

	# Decide what is a match and what not
	cursor.execute(
		"SELECT calculated_issue_number, date FROM issues WHERE volume_id = ?;",
		(volume_id,)
	)
	issue_numbers = {i[0]: int(i[1].split('-')[0]) if i[1] else None for i in cursor}
	for result in results:
		result.update(
			_check_match(result, title, volume_number, special_version, issue_numbers, calculated_issue_number, year)
		)

	# Sort results; put best result at top
	results.sort(key=lambda r: _sort_search_results(r, title, volume_number, year, calculated_issue_number))
		
	logging.debug(f'Manual search results: {results}')
	return results

def auto_search(volume_id: int, issue_id: int=None) -> List[dict]:
	"""Search for a volume or issue and automatically choose a result

	Args:
		volume_id (int): The id of the volume to search for
		issue_id (int, optional): The id of the issue to search for
		(in the case that you want to search for an issue instead of a volume). 
		Defaults to None.

	Returns:
		List[dict]: List with chosen search results.
	"""	
	# Get data about volume (and issue)
	cursor = get_db()
	cursor.execute("""
		SELECT
			monitored, special_version
		FROM volumes
		WHERE id = ?
		LIMIT 1;
		""",
		(volume_id,)
	)
	volume_monitored, special_version = cursor.fetchone()
	logging.info(
		f'Starting auto search for volume {volume_id} {f"issue {issue_id}" if issue_id else ""}'
	)
	if not volume_monitored:
		# Volume is unmonitored so regardless of what to search for, ignore searching
		result = []
		logging.debug(f'Auto search results: {result}')
		return result

	if issue_id is None:
		# Auto search volume
		issue_number = None
		# Get issue numbers that are open (monitored and no file)
		cursor.execute(
			"""
			SELECT calculated_issue_number
			FROM issues i
			LEFT JOIN issues_files if
			ON i.id = if.issue_id
			WHERE
				file_id IS NULL
				AND volume_id = ?
				AND monitored = 1;
			""",
			(volume_id,)
		)
		searchable_issues = tuple(map(lambda i: i[0], cursor))
		if not searchable_issues:
			result = []
			logging.debug(f'Auto search results: {result}')
			return result

	else:
		# Auto search issue
		cursor.execute(
			"SELECT issue_number, monitored FROM issues WHERE id = ? LIMIT 1",
			(issue_id,)
		)
		issue_number, monitored = cursor.fetchone()
		if not monitored:
			# Auto search for issue but issue is unmonitored
			result = []
			logging.debug(f'Auto search results: {result}')
			return result
		else:
			cursor.execute(
				"SELECT 1 FROM issues_files WHERE issue_id = ? LIMIT 1",
				(issue_id,)
			)
			if (1,) in cursor:
				# Auto search for issue but issue already has file
				result = []
				logging.debug(f'Auto search results: {result}')
				return result

	results = list(filter(
		lambda r: r['match'],
		manual_search(volume_id, issue_id)
	))
	if issue_number is not None or special_version:
		result = []
		if results:
			result.append(results[0])
		logging.debug(f'Auto search results: {result}')
		return result
	else:
		volume_parts = []
		for result in results:
			if result['issue_number'] is not None:
				if isinstance(result['issue_number'], tuple):
					# Release is an issue range
					# Only allow range if all the issues that the range covers are open
					covered_issues = tuple(map(lambda i: i[0], cursor.execute("""
						SELECT calculated_issue_number
						FROM issues
						WHERE
							volume_id = ?
							AND calculated_issue_number >= ?
							AND calculated_issue_number <= ?;
					""", (volume_id, *result['issue_number']))))
					if any(not i in searchable_issues for i in covered_issues):
						continue
				else:
					# Release is a specific issue
					if not result['issue_number'] in searchable_issues:
						continue

				# Check that any other selected download doesn't already cover the issue
				for part in volume_parts:
					if isinstance(result['issue_number'], tuple):
						# Release is an issue range
						for is_n in result['issue_number']:
							if part['issue_number'][0] <= is_n <= part['issue_number'][1]:
								break
						else:
							continue
						break
					else:
						# Release is a specific issue
						if isinstance(part['issue_number'], tuple):
							if part['issue_number'][0] <= result['issue_number'] <= part['issue_number'][1]:
								break
						else:
							if part['issue_number'] == result['issue_number']:
								break
				else:
					volume_parts.append(result)
		
		logging.debug(f'Auto search results: {volume_parts}')
		return volume_parts
