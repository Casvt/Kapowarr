#-*- coding: utf-8 -*-

"""This file contains functions to interract with the comicvine api
"""

import logging
from re import compile
from typing import List

from bs4 import BeautifulSoup
from requests import Session
from requests.exceptions import ConnectionError as requests_ConnectionError

from backend.custom_exceptions import InvalidComicVineApiKey, VolumeNotMatched
from backend.db import get_db
from backend.files import process_issue_number
from backend.settings import Settings, private_settings

volume_search = compile(r'(?i)(?:v(?:ol(?:ume)?)?[\.\s]*)(\d+)')

def _clean_description(description: str) -> str:
	"""Reduce size of description (written in html) to only essential information

	Args:
		description (str): The description (written in html) to clean

	Returns:
		str: The cleaned description (written in html)
	"""	
	logging.debug(f'Cleaning the description: {description}')
	if not description:
		return description

	soup = BeautifulSoup(description, 'html.parser')
	# Remove images, titles and lists
	for el in soup.find_all(["figure","img","h2","h3","h4","h5","h6","ul","ol","p"]):
		if el.name == 'p':
			above_els = [e for e in getattr(el, 'children', [])]
			if not (1 <= len(above_els) <= 2 and above_els[0].name in ('b','i')):
				continue

		el.decompose()

	# Fix links
	for link in soup.find_all('a'):
		link['target'] = '_blank'
		link.attrs = {k: v for k, v in link.attrs.items() if not k.startswith('data-')}
		link['href'] = link['href'].lstrip('./')
		if not link['href'].startswith('http'):
			link['href'] = private_settings['comicvine_url'] + '/' + link['href']

	result = str(soup)
	logging.debug(f'Cleaned description result: {result}')
	return result

class ComicVine:
	"""Used for interacting with ComicVine
	"""	
	volume_field_list = ','.join(('deck', 'description', 'id', 'image', 'issues', 'name', 'publisher', 'start_year', 'count_of_issues'))
	search_field_list = ','.join(('aliases', 'count_of_issues', 'deck', 'description', 'id', 'image', 'name', 'publisher', 'site_detail_url', 'start_year'))
	
	def __init__(self) -> None:
		"""Start interacting with ComicVine

		Raises:
			InvalidComicVineApiKey: No ComicVine API key is set in the settings
		"""
		self.api_url = private_settings['comicvine_api_url']
		api_key = Settings().get_settings()['comicvine_api_key']
		if not api_key:
			raise InvalidComicVineApiKey

		self.ssn = Session()
		self.ssn.params.update({'format': 'json', 'api_key': api_key})
		self.ssn.headers.update({'user-agent': 'Kapowarr'})
		return

	def __format_volume_output(self, volume_data: dict) -> dict:
		"""Format the ComicVine API output containing the info about the volume to the "Kapowarr format"

		Args:
			volume_data (dict): The ComicVine API output

		Returns:
			dict: The formatted version
		"""		
		logging.debug(f'Formating volume output: {volume_data}')
		result = {
			'comicvine_id': int(volume_data['id']),
			'title': volume_data['name'],
			'year': int(volume_data['start_year'].replace('-', '0')) if volume_data['start_year'] is not None else None,
			'cover': volume_data['image']['small_url'],
			'publisher': volume_data['publisher']['name'],
			'issue_count': int(volume_data['count_of_issues'])
		}
		
		# Extract volume number
		match = volume_search.search(volume_data['deck'] or '')
		result['volume_number'] = int(match.group(1)) if match else 1
		
		# Format description
		result['description'] = _clean_description(volume_data['description'])

		# Turn aliases into list
		if 'aliases' in volume_data:
			if volume_data['aliases']:
				result['aliases'] = volume_data['aliases'].split('\r\n')
			else:
				result['aliases'] = []
				
		# Covert other keys if present
		if 'site_detail_url' in volume_data:
			result['comicvine_info'] = volume_data['site_detail_url']

		logging.debug(f'Formatted volume output result: {result}')		
		return result
		
	def __format_issue_output(self, issue_data: dict) -> dict:
		"""Format the ComicVine API output containing the info about the issue to the "Kapowarr format"

		Args:
			issue_data (dict): The ComicVine API output

		Returns:
			dict: The formatted version
		"""		
		logging.debug(f'Formatting issue output: {issue_data}')
		result = {
			'comicvine_id': issue_data['id'],
			'issue_number': issue_data['issue_number'],
			'calculated_issue_number': process_issue_number(issue_data['issue_number']),
			'title': issue_data['name'] or None,
			'date': issue_data['cover_date'] or None,
			'description': _clean_description(issue_data['description'])
		}
		logging.debug(f'Formatted issue output result: {result}')
		return result

	def fetch_volume(self, id: str) -> dict:
		"""Get the metadata of a volume from ComicVine, formatted to the "Kapowarr format"

		Args:
			id (str): The comicvine id of the volume. The `4050-` prefix is optional.

		Raises:
			VolumeNotMatched: No comic in the ComicVine database matches with the given id

		Returns:
			dict: The metadata of the volume
		"""		
		if not id.startswith('4050-'):
			id = '4050-' + id
		logging.debug(f'Fetching volume data for {id}')
		
		# Fetch volume info
		result = self.ssn.get(
			f'{self.api_url}/volume/{id}',
			params={'field_list': self.volume_field_list}
		).json()
		if result['status_code'] == 101:
			raise VolumeNotMatched

		volume_info = self.__format_volume_output(result['results'])

		# Fetch cover
		try:
			volume_info['cover'] = self.ssn.get(volume_info['cover']).content
		except requests_ConnectionError:
			volume_info['cover'] = None

		# Fetch issues
		logging.debug(f'Fetching issue data for volume {id}')
		volume_info['issues'] = []
		for offset in range(0, volume_info['issue_count'], 100):
			results = self.ssn.get(
				f'{self.api_url}/issues',
				params={'filter': f'volume:{volume_info["comicvine_id"]}',
					'offset': offset}
			).json()['results']
			for issue in results:
				volume_info['issues'].append(
					self.__format_issue_output(issue)
				)

		logging.debug(f'Fetching volume data result: {volume_info}')
		return volume_info
		
	def search_volumes(self, query: str) -> List[dict]:
		"""Search for volumes in the ComicVine database

		Args:
			query (str): The query to use when searching

		Returns:
			List[dict]: A list with search results
		"""		
		logging.debug(f'Searching for volumes with the query {query}')
		cursor = get_db()

		# Fetch comicvine results
		results: list
		if query.startswith('cv:'):
			query = query.partition(':')[2]
			if not query.startswith('4050-'):
				query = '4050-' + query
			if not query.replace('-','0').isdigit():
				return []
			results = [
				self.ssn.get(
					f'{self.api_url}/volume/{query}',
					params={'field_list': self.search_field_list}
				).json()['results']
			]
			if results == [[]]:
				return []
		else:
			results = self.ssn.get(
				f'{self.api_url}/volumes',
				params={'filter': f'name:{query}',
						'limit': 50,
						'field_list': self.search_field_list}
			).json()['results']
			if not results:
				return []

		# Remove entries that are already added
		logging.debug('Removing entries that are already added')
		volume_ids = cursor.execute(
			"SELECT comicvine_id FROM volumes;"
		).fetchall()
		results = list(filter(
			lambda v: not (v['id'],) in volume_ids,
			results
		))
		
		# Format results
		for i, result in enumerate(results):
			results[i] = self.__format_volume_output(result)
		
		# Sort results (prefer direct title matches and then sort those on volume number)
		if len(results) > 1:
			results.sort(
				key=lambda v: (
					0 if v['title'] == query else 1,
					v['volume_number'] or float('inf') if v['title'] == query else float('inf') + 1
				)
			)
		
		logging.debug(f'Searching for volumes with query result: {results}')
		return results
		