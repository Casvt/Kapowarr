#-*- coding: utf-8 -*-

"""
Searching online sources (GC) for downloads
"""

import logging
from asyncio import create_task, gather, run
from typing import Dict, List, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from requests import get

from backend.db import get_db
from backend.enums import SpecialVersion
from backend.file_extraction import extract_filename_data
from backend.helpers import (MatchedSearchResultData, SearchResultData,
                             check_overlapping_issues, create_range,
                             extract_year_from_date, first_of_column)
from backend.matching import _match_special_version, check_search_result_match
from backend.settings import private_settings
from backend.volumes import Issue, Volume, get_calc_number_range


def _sort_search_results(
	result: MatchedSearchResultData,
	title: str,
	volume_number: int,
	year: Union[int, None] = None,
	calculated_issue_number: Union[float, None] = None
) -> List[int]:
	"""Sort the search results

	Args:
		result (MatchedSearchResultData): A result from `search.SearchSources.search_all()`.

		title (str): Title of volume

		volume_number (int): The volume number of the volume

		year (Union[int, None], optional): The year of the volume.
			Defaults to None.

		calculated_issue_number (Union[float, None], optional): The
		calculated_issue_number of the issue.
			Defaults to None.

	Returns:
		List[int]: A list of numbers which determines the ranking of the result.
	"""
	rating = []

	# Prefer matches
	rating.append(int(not result['match']))

	# The more words in the search term that are present in
	# the search results' title, the higher ranked it gets
	split_title = title.split(' ')
	rating.append(len([
		word
		for word in result['series'].split(' ')
		if not word in split_title
	]))

	# Prefer volume number or year matches, even better if both match
	v_match = int(not (
		result['volume_number'] is not None
		and result['volume_number'] == volume_number
	))
	y_match = int(not (
		year is not None
		and result['year'] is not None
		and year - 1 <= result['year'] <= year + 1
	))
	rating.append(v_match + y_match)

	# Sort on issue number fitting
	if calculated_issue_number is not None:
		if (isinstance(result['issue_number'], float)
		and calculated_issue_number == result['issue_number']):
			# Issue number is direct match
			rating.append(0)

		elif isinstance(result['issue_number'], tuple):
			if result['issue_number'][0] <= calculated_issue_number <= result['issue_number'][1]:
				# Issue number falls between range
				rating.append(
					1 - (1
						/
						(result['issue_number'][1] - result['issue_number'][0] + 1))
				)
			else:
				# Issue number falls outside so release is not usefull
				rating.append(3)

		elif (result['issue_number'] is None
		and result['special_version'] is not None):
			# Issue number not found but is special version
			rating.append(2)

		else:
			rating.append(3)
	else:
		if isinstance(result['issue_number'], tuple):
			rating.append(
				1.0
				/
				(result['issue_number'][1] - result['issue_number'][0] + 1)
			)

		elif isinstance(result['issue_number'], float):
			rating.append(1)

	return rating

class SearchSources:
	"For getting search results from various sources"

	def __init__(self, query: str):
		"""Prepare a search

		Args:
			query (str): The search string to search for in the sources
		"""
		self.query = query
		self.source_list = [
			self._get_comics,
		]

	def search_all(self) -> List[SearchResultData]:
		"Search all sources for the query"
		result: List[SearchResultData] = []
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

	def _get_comics(self) -> List[SearchResultData]:
		"""Search for the query in getcomics

		Returns:
			List[SearchResultData]: The search results
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

		formatted_results: List[SearchResultData] = []
		for result in results:
			link = result.find('a')['href']
			title = (result
				.find("h1", {"class": "post-title"})
				.get_text(strip=True)
			)

			data = extract_filename_data(
				title,
				assume_volume_number=False,
				fix_year=True
			)
			formatted_results.append(SearchResultData(**{
				**data,
				'link': link,
				'display_title': title,
				'source': 'GetComics'
			}))

		return formatted_results

def manual_search(
	volume_id: int,
	issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
	"""Do a manual search for a volume or issue

	Args:
		volume_id (int): The id of the volume to search for
		issue_id (Union[int, None], optional): The id of the issue to search for
		(in the case that you want to search for an issue instead of a volume).
		Defaults to None.

	Returns:
		List[MatchedSearchResultData]: List with search results.
	"""
	volume = Volume(volume_id)
	volume_data = volume.get_keys(
		('title', 'volume_number', 'year', 'special_version')
	)

	if issue_id and not volume_data.special_version.value:
		issue_data = Issue(issue_id).get_keys(
			('issue_number', 'calculated_issue_number')
		)
		issue_number: Union[str, None] = issue_data['issue_number']
		calculated_issue_number: Union[float, None] = issue_data[
			'calculated_issue_number'
		]

	else:
		issue_number: Union[str, None] = None
		calculated_issue_number: Union[float, None] = None

	logging.info(
		f'Starting manual search: {volume_data.title} ({volume_data.year}) {"#" + issue_number if issue_number else ""}'
	)

	# Prepare query
	title = volume_data.title.replace(':', '')

	if volume_data.special_version == SpecialVersion.TPB:
		query_formats = (
			'{title} Vol. {volume_number} ({year}) TPB',
			'{title} ({year}) TPB',
			'{title} Vol. {volume_number} TPB',
			'{title} Vol. {volume_number}',
			'{title}'
		)
	elif volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE:
		query_formats = (
			'{title} ({year})',
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

	if volume_data.year is None:
		query_formats = tuple(f.replace('({year})', '') for f in query_formats)

	# Get formatted search results
	search_results: List[SearchResultData] = []
	for format in query_formats:
		search = SearchSources(
			format.format(
				title=title, volume_number=volume_data.volume_number,
				year=volume_data.year, issue_number=issue_number
			)
		)
		search_results += search.search_all()

	# Remove duplicates
	# because multiple formats can return the same result
	search_results = list({r['link']: r for r in search_results}.values())

	# Decide what is a match and what not
	issue_numbers: Dict[float, Union[int, None]] = {
		i['calculated_issue_number']: extract_year_from_date(i['date'])
		for i in volume.get_issues()
	}
	results = [
		MatchedSearchResultData({
			**result,
			**check_search_result_match(result, volume_id, title,
				volume_data.special_version, issue_numbers,
				calculated_issue_number, volume_data.year
			)
		})
		for result in search_results
	]

	# Sort results; put best result at top
	results.sort(key=lambda r: _sort_search_results(
		r, title, volume_data.volume_number, volume_data.year,
		calculated_issue_number
	))

	logging.debug(f'Manual search results: {results}')
	return results

def auto_search(
	volume_id: int,
	issue_id: Union[int, None] = None
) -> List[MatchedSearchResultData]:
	"""Search for a volume or issue and automatically choose a result

	Args:
		volume_id (int): The id of the volume to search for
		issue_id (Union[int, None], optional): The id of the issue to search for
		(in the case that you want to search for an issue instead of a volume).
		Defaults to None.

	Returns:
		List[MatchedSearchResultData]: List with chosen search results.
	"""
	cursor = get_db()

	volume = Volume(volume_id)
	monitored = volume['monitored']
	special_version = volume['special_version']
	logging.info(
		f'Starting auto search for volume {volume_id} {f"issue {issue_id}" if issue_id else ""}'
	)
	if not monitored:
		# Volume is unmonitored so regardless of what to search for, ignore searching
		result = []
		logging.debug(f'Auto search results: {result}')
		return result

	searchable_issues: List[float] = []
	if issue_id is None:
		# Auto search volume
		# Get issue numbers that are open (monitored and no file)
		searchable_issues: List[float] = first_of_column(cursor.execute(
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
		))
		if not searchable_issues:
			result = []
			logging.debug(f'Auto search results: {result}')
			return result

	else:
		# Auto search issue
		issue = Issue(issue_id)
		if not issue['monitored']:
			# Auto search for issue but issue is unmonitored
			result = []
			logging.debug(f'Auto search results: {result}')
			return result
		else:
			if issue.get_files():
				# Auto search for issue but issue already has file
				result = []
				logging.debug(f'Auto search results: {result}')
				return result

	results = [r for r in manual_search(volume_id, issue_id) if r['match']]

	if issue_id is not None or (
		special_version.value is not None
		and special_version != SpecialVersion.VOLUME_AS_ISSUE
	):
		result = results[:1] if results else []
		logging.debug(f'Auto search results: {result}')
		return result

	volume_parts = []
	for result in results:
		if not _match_special_version(
				special_version,
				result['special_version'],
				result['issue_number']
		):
			continue

		if result['issue_number'] is not None:
			# Normal issue, VAS with issue number,
			# OS/HC using issue 1
			result['_issue_number'] = result['issue_number']
			covered_issues = get_calc_number_range(
				volume_id,
				*create_range(result['issue_number'])
			)

		elif (special_version == SpecialVersion.VOLUME_AS_ISSUE
		and result['special_version'] == SpecialVersion.TPB):
			# VAS with volume number
			if result['volume_number'] is None:
				continue

			if isinstance(result['volume_number'], tuple):
				result['_issue_number'] = (
					float(result['volume_number'][0]),
					float(result['volume_number'][1])
				)
			else:
				result['_issue_number'] = float(result['volume_number'])

			covered_issues = get_calc_number_range(
				volume_id,
				*create_range(result['volume_number'])
			)

		elif (
			special_version in (
				SpecialVersion.ONE_SHOT,
				SpecialVersion.HARD_COVER,
				SpecialVersion.TPB
			)
			and result['special_version'] in (
				special_version,
				SpecialVersion.TPB
			)
		):
			# OS/HC using no issue number, TPB
			result['_issue_number'] = 1.0
			covered_issues = (1.0,)

		else:
			continue

		if any(not i in searchable_issues for i in covered_issues):
			continue

		# Check that any other selected download doesn't already cover the issue
		for part in volume_parts:
			if check_overlapping_issues(
				part['_issue_number'],
				result['_issue_number']
			):
				break
		else:
			volume_parts.append(result)

	logging.debug(f'Auto search results: {volume_parts}')
	return volume_parts
