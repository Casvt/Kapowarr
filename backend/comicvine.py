#-*- coding: utf-8 -*-

"""This file contains functions to interract with the comicvine api
"""

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
	if not description:
		return ''

	soup = BeautifulSoup(description, 'html.parser')
	#remove images, titles and lists
	for el in soup.find_all(["figure","img","h2","h3","h4","h5","h6","ul","ol","p"]):
		if el.name == 'p':
			above_els = [e for e in getattr(el, 'children', [])]
			if not (1 <= len(above_els) <= 2 and above_els[0].name in ('b','i')):
				continue

		el.decompose()

	#fix links
	for link in soup.find_all('a'):
		link['target'] = '_blank'
		link.attrs = {k: v for k, v in link.attrs.items() if not k.startswith('data-')}
		link['href'] = link['href'].lstrip('./')
		if not link['href'].startswith('http'):
			link['href'] = 'https://comicvine.gamespot.com/' + link['href']

	return str(soup)

class ComicVine:
	volume_field_list = ','.join(('deck', 'description', 'id', 'image', 'issues', 'name', 'publisher', 'start_year', 'count_of_issues'))
	search_field_list = ','.join(('aliases', 'count_of_issues', 'deck', 'description', 'id', 'image', 'name', 'publisher', 'site_detail_url', 'start_year'))
	
	def __init__(self):
		self.api_url = private_settings['comicvine_api_url']
		api_key = Settings().get_settings()['comicvine_api_key']
		if not api_key:
			raise InvalidComicVineApiKey

		self.ssn = Session()
		self.ssn.params.update({'format': 'json', 'api_key': api_key})
		self.ssn.headers.update({'user-agent': 'Kapowarr'})

	def __format_volume_output(self, volume_data: dict) -> dict:
		result = {
			'comicvine_id': int(volume_data['id']),
			'title': volume_data['name'],
			'year': int(volume_data['start_year'].replace('-', '0')),
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
		
		return result
		
	def __format_issue_output(self, issue_data: dict) -> dict:
		result = {
			'comicvine_id': issue_data['id'],
			'issue_number': issue_data['issue_number'],
			'calculated_issue_number': process_issue_number(issue_data['issue_number']),
			'title': issue_data['name'],
			'date': issue_data['cover_date'],
			'description': _clean_description(issue_data['description'])
		}
		return result

	def fetch_volume(self, id: str) -> dict:
		if not id.startswith('4050-'):
			id = '4050-' + id
		
		# Fetch volume info
		result = self.ssn.get(f'{self.api_url}/volume/{id}', params={'field_list': self.volume_field_list}).json()
		if result['status_code'] == 101:
			raise VolumeNotMatched

		volume_info: dict = self.__format_volume_output(result['results'])

		# Fetch cover
		try:
			volume_info['cover'] = self.ssn.get(volume_info['cover']).content
		except requests_ConnectionError:
			volume_info['cover'] = None

		# Fetch issues
		volume_info['issues'] = []
		for offset in range(0, volume_info['issue_count'], 100):
			results = self.ssn.get(f'{self.api_url}/issues', params={'filter': f'volume:{volume_info["comicvine_id"]}', 'offset': offset}).json()['results']
			for issue in results:
				volume_info['issues'].append(
					self.__format_issue_output(issue)
				)

		return volume_info
		
	def search_volumes(self, query: str) -> List[dict]:
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

		return results
		