#-*- coding: utf-8 -*-

"""This file contains functions regarding searching for a volume or issue with getcomics.info as the source

Inspired by Mylar3:
	https://github.com/mylar3/mylar3/blob/master/mylar/getcomics.py#L163
"""

import logging
from re import compile
from typing import List

from bs4 import BeautifulSoup
from requests import get

from backend.blocklist import blocklist_contains
from backend.db import get_db
from backend.files import extract_filename_data, process_issue_number
from backend.settings import private_settings

clean_title_regex_1 = compile(r'[/:]')
clean_title_regex_2 = compile(r'(\-|\+|,|\!|:|\bthe\b)')
strip_spaces = compile(r'\s+')

def _check_matching_titles(title1: str, title2: str) -> bool:
	pre_clean_title = clean_title_regex_2.sub('', title1.lower())
	clean_reference_title = strip_spaces.sub(' ', pre_clean_title).strip()
	pre_clean_title = clean_title_regex_2.sub('', title2.lower())
	clean_title = strip_spaces.sub(' ', pre_clean_title).strip()

	return clean_reference_title == clean_title

def _check_match(result: dict, title: str, calculated_issue_number: float, year: int) -> dict:
	if blocklist_contains(result['link']):
		return {'match': False, 'match_issue': 'Link is blocklisted'}

	if not _check_matching_titles(title, result['series']):
		return {'match': False, 'match_issue': 'Title doesn\'t match'}
	
	issue_number_is_equal = (
		calculated_issue_number is None
		or
		(
			isinstance(result['issue_number'], float)
			and calculated_issue_number == result['issue_number']
		)
	)
	if not issue_number_is_equal:
		return {'match': False, 'match_issue': 'Issue number(s) don\'t match'}
	
	year_is_equal = (
		year is None
		or result['year'] is None
		or year - 1 <= result['year'] <= year + 1
	)
	if not year_is_equal:
		return {'match': False, 'match_issue': 'Year doesn\'t match'}
		
	return {'match': True, 'match_issue': None}

def _sort_search_results(r, title, year: int=None, issue_number: int=None) -> List[int]:
	rating = []

	# Prefer matches
	rating.append(int(not r['match']))

	# The more words in the search term that are present in the search results' title, 
	# the higher ranked it gets
	split_title = title.split(' ')
	rating.append(len([word for word in r['series'].split(' ') if not word in split_title]))

	# Bonus if the year matches
	if year is not None:
		if r['year'] == year:
			rating.append(0)
		else:
			rating.append(1)

	# Sort on issue number fitting
	if issue_number is not None:
		if isinstance(r['issue_number'], float) and issue_number == r['issue_number']:
			#issue number is direct match
			rating.append(0)

		elif isinstance(r['issue_number'], str):
			split_issue_number = tuple(map(float, r['issue_number'].split('-')))
			if split_issue_number[0] <= issue_number <= split_issue_number[1]:
				#issue number falls between range
				rating.append(1 - (1 / (split_issue_number[1] - split_issue_number[0] + 1)))
			else:
				#issue number falls outside so release is not usefull
				rating.append(3)

		elif r['issue_number'] == None and r['special_version'] != None:
			#issue number not found but is special version
			rating.append(2)

		else:
			rating.append(3)
	else:
		if isinstance(r['issue_number'], str):
			split_issue_number = tuple(map(float, r['issue_number'].split('-')))
			rating.append(1.0 / (split_issue_number[1] - split_issue_number[0] + 1))

		elif isinstance(r['issue_number'], float):
			rating.append(1)

	return rating

class SearchSources:
	def __init__(self, query: str):
		self.search_results: List[dict] = []
		self.query = query
		self.source_list = [
			self.get_comics,
			self.indexers
		]

	def search_all(self) -> None:
		for source in self.source_list:
			self.search_results += source()
		return

	def get_comics(self) -> None:
		search_results = get(private_settings["getcomics_url"], params={'s': self.query}, timeout=30).text
		soup = BeautifulSoup(search_results, 'html.parser')
		pages = soup.find_all(['a','span'], {"class": 'page-numbers'})
		pages = max(int(pages[-1].get_text(strip=True)), 10) if pages else 1

		results = []
		for page in range(1, pages + 1):
			if page > 1:
				search_results = get(f'{private_settings["getcomics_url"]}/page/{page}', params={'s': self.query}, timeout=30).text
				soup = BeautifulSoup(search_results, 'html.parser')
			results += soup.find_all('article', {"class": "post"})

		formatted_results = []
		for result in results:
			link = result.find('a')['href']
			title = result.find("h1", {"class": "post-title"}).get_text(strip=True)

			data = extract_filename_data(title)
			data.update({
				'link': link,
				'display_title': title,
				'source': 'GetComics'
			})
			formatted_results.append(data)
		
		return formatted_results
	
	def indexers(self) -> None:
		return []

def manual_search(title, volume_number: int, year: int=None, issue_number: str=None) -> List[dict]:
	logging.info(f'Starting manual search: {title} ({year}) {"#" + issue_number if issue_number else ""}')

	if issue_number is not None:
		calculated_issue_number = process_issue_number(issue_number)
	else:
		calculated_issue_number = None

	# Prepare query
	title = clean_title_regex_1.sub('', title)

	if issue_number is None:
		query_formats = ('{title} Vol. {volume_number} ({year})', '{title} ({year})', '{title} Vol. {volume_number}')
	else:
		query_formats = ('{title} #{issue_number} ({year})', '{title} Vol. {volume_number} #{issue_number}', '{title} #{issue_number}')

	if year is None:
		query_formats = tuple(f.replace('({year})', '') for f in query_formats)

	# Get formatted search results
	results = []
	for format in query_formats:
		search = SearchSources(
			format.format(title=title, volume_number=volume_number, year=year, issue_number=issue_number)
		)
		search.search_all()
		results += search.search_results

	# Remove duplicates 
	# because multiple formats can return the same result
	results = list({r['link']: r for r in results}.values())

	# Decide what is a match and what not
	for result in results:
		result.update(_check_match(result, title, calculated_issue_number, year))

	# Sort results; put best result at top
	results.sort(key=lambda r: _sort_search_results(r, title, year, calculated_issue_number))
		
	logging.debug(f'Manual search results: {results}')
	return results

def auto_search(volume_id: int, issue_id: int=None) -> List[dict]:
	#get data about volume (and issue)
	cursor = get_db()
	cursor.execute("SELECT title, volume_number, year, monitored FROM volumes WHERE id = ? LIMIT 1", (volume_id,))
	title, volume_number, year, volume_monitored = cursor.fetchone()
	logging.info(f'Starting auto search for volume {volume_id} {f"issue {issue_id}" if issue_id else ""}')
	if not volume_monitored:
		#volume is unmonitored so regardless of what to search for, ignore searching
		result = []
		logging.debug(f'Auto search results: {result}')
		return result

	if issue_id is None:
		#auto search volume
		issue_number = None
		#get issue numbers that are open (monitored and no file)
		cursor.execute(
			"""
			SELECT
				i.calculated_issue_number
			FROM
				issues AS i
			WHERE
				i.volume_id = ?
				AND i.monitored = 1
				AND NOT EXISTS(
					SELECT 1
					FROM
						issues_files AS if
					WHERE
						if.issue_id = i.id
				);
			""",
			(volume_id,)
		)
		searchable_issues = tuple(map(lambda i: i[0], cursor.fetchall()))
		if not searchable_issues:
			result = []
			logging.debug(f'Auto search results: {result}')
			return result
	else:
		#auto search issue
		cursor.execute(
			"SELECT issue_number, monitored FROM issues WHERE id = ? LIMIT 1",
			(issue_id,)
		)
		issue_number, monitored = cursor.fetchone()
		if not monitored:
			#auto search for issue but issue is unmonitored
			result = []
			logging.debug(f'Auto search results: {result}')
			return result
		else:
			cursor.execute(
				"SELECT issue_id FROM issues_files WHERE issue_id = ? LIMIT 1",
				(issue_id,)
			)
			if cursor.fetchone() is not None:
				#auto search for issue but issue already has file
				result = []
				logging.debug(f'Auto search results: {result}')
				return result

	results = filter(
		lambda r: r['match'] == True,
		manual_search(title, volume_number, year, issue_number)
	)
	if issue_number is not None:
		result = [next(iter(results), {})]
		if result == [{}]:
			result = []
		logging.debug(f'Auto search results: {result}')
		return result
	else:
		volume_parts = []
		for result in results:
			if result['special_version'] is not None:
				result = [result]
				logging.debug(f'Auto search results: {result}')
				return result
			elif result['issue_number'] is not None:
				if isinstance(result['issue_number'], tuple):
					#release is an issue range
					#if all issues in the range this release covers are not open for search, don't include release
					if not filter(
						lambda i: result['issue_number'][0] <= i <= result['issue_number'][1],
						searchable_issues
					):
						continue
				else:
					#release is a specific issue
					if not result['issue_number'] in searchable_issues:
						continue

				for part in volume_parts:
					if isinstance(result['issue_number'], tuple):
						#release is an issue range
						for is_n in result['issue_number']:
							if part['issue_number'][0] <= is_n <= part['issue_number'][1]:
								break
						else:
							continue
						break
					else:
						#release is a specific issue
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
