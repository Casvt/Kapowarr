#-*- coding: utf-8 -*-

"""
Search for volumes/issues and fetch metadata for them on ComicVine
"""

from backend.logging import LOGGER
from asyncio import create_task, gather
from re import IGNORECASE, compile
from typing import Any, Dict, List, Union

from aiohttp import ClientSession
from aiohttp.client_exceptions import ContentTypeError
from bs4 import BeautifulSoup, Tag
from requests import Session
from requests.exceptions import ConnectionError as requests_ConnectionError
from simplejson import JSONDecodeError

from backend.custom_exceptions import (CVRateLimitReached,
                                       InvalidComicVineApiKey,
                                       VolumeNotMatched)
from backend.db import get_db
from backend.file_extraction import (convert_volume_number_to_int,
                                     process_issue_number, volume_regex)
from backend.helpers import T, batched, normalize_string
from backend.settings import Settings, private_settings

translation_regex = compile(
	r'^<p>\s*\w+ publication(\.?</p>$|,\s| \(in the \w+ language\)|, translates )|' +
	r'^<p>\s*published by the \w+ wing of|' +
	r'^<p>\s*\w+ translations? of|' +
	r'from \w+</p>$|' +
	r'^<p>\s*published in \w+|' +
	r'^<p>\s*\w+ language|' +
	r'^<p>\s*\w+ edition of|' +
	r'^<p>\s*\w+ reprint of|' +
	r'^<p>\s*\w+ trade collection of',
	IGNORECASE
)
headers = {'h2', 'h3', 'h4', 'h5', 'h6'}
lists = {'ul', 'ol'}

def _clean_description(description: str, short: bool=False) -> str:
	"""Reduce size of description (written in html) to only essential information

	Args:
		description (str): The description (written in html) to clean.
		short (bool, optional): Only remove images and fix links.
			Defaults to False.

	Returns:
		str: The cleaned description (written in html)
	"""
	if not description:
		return description

	soup = BeautifulSoup(description, 'html.parser')

	# Remove images
	for el in soup.find_all(["figure", "img"]):
		el.decompose()

	if not short:
		# Remove everything after the first title with list
		removed_elements = []
		for el in soup:
			if not isinstance(el, Tag):
				continue
			if el.name is None:
				continue

			if (removed_elements
			or el.name in headers):
				removed_elements.append(el)
				continue

			if el.name in lists:
				removed_elements.append(el)
				prev_sib = el.previous_sibling
				if (prev_sib is not None
				and prev_sib.text.endswith(':')):
					removed_elements.append(prev_sib)
				continue

			if el.name == 'p':
				children = list(getattr(el, 'children', []))
				if (1 <= len(children) <= 2
				and children[0].name in ('b', 'i', 'strong')):
					removed_elements.append(el)

		for el in removed_elements:
			if isinstance(el, Tag):
				el.decompose()

	# Fix links
	for link in soup.find_all('a'):
		link['target'] = '_blank'
		link.attrs = {
			k: v for k, v in link.attrs.items() if not k.startswith('data-')
		}
		link['href'] = link['href'].lstrip('./')
		if not link['href'].startswith('http'):
			link['href'] = private_settings['comicvine_url'] + '/' + link['href']

	result = str(soup)
	return result

class ComicVine:
	"""Used for interacting with ComicVine
	"""
	volume_field_list = ','.join(('deck', 'description', 'id', 'image', 'issues', 'name', 'publisher', 'start_year', 'count_of_issues'))
	issue_field_list = ','.join(('id', 'issue_number', 'name', 'cover_date', 'description', 'volume'))
	search_field_list = ','.join(('aliases', 'count_of_issues', 'deck', 'description', 'id', 'image', 'name', 'publisher', 'site_detail_url', 'start_year'))

	def __init__(self, comicvine_api_key: Union[str, None] = None) -> None:
		"""Start interacting with ComicVine

		Args:
			comicvine_api_key (Union[str, None], optional): Override the API key that is used.
				Defaults to None.

		Raises:
			InvalidComicVineApiKey: No ComicVine API key is set in the settings
		"""
		self.api_url = private_settings['comicvine_api_url']
		if comicvine_api_key:
			api_key = comicvine_api_key
		else:
			api_key = Settings()['comicvine_api_key']
		if not api_key:
			raise InvalidComicVineApiKey

		self.ssn = Session()
		self._params = {'format': 'json', 'api_key': api_key}
		self._headers = {'user-agent': 'Kapowarr'}
		self.ssn.params.update(self._params) # type: ignore
		self.ssn.headers.update(self._headers)
		return

	def __normalize_cv_id(self, cv_id: str) -> str:
		"""Turn user entered cv id in to formatted id

		Args:
			cv_id (str): The user entered cv id

		Raises:
			VolumeNotMatched: Invalid ID.

		Returns:
			str: The cv id as `4050-NNNN`.
		"""
		if cv_id.startswith('cv:'):
			cv_id = cv_id.partition(':')[2]

		if not cv_id.startswith('4050-'):
			cv_id = '4050-' + cv_id

		if cv_id.replace('-','0').isdigit():
			return cv_id

		raise VolumeNotMatched

	async def __call_request_async(self,
		session: ClientSession,
		url: str
	) -> Union[bytes, None]:
		"""Fetch a URL and get it's content async (with error handling).

		Args:
			session (ClientSession): The aiohttp session to make the request with.
			url (str): The URL to make the request to.

		Returns:
			Union[bytes, None]: The content in bytes.
				`None` in case of error.
		"""
		try:
			async with session.get(url) as response:
				return await response.content.read()

		except (ContentTypeError, requests_ConnectionError):
			return None

	def __call_api(self,
		url_path: str,
		params: dict
	) -> dict:
		"""Make an CV API call (with error handling).

		Args:
			url_path (str): The path of the url to make the call to (e.g. '/volumes').
				Beginning '/' required.

			params (dict): The URL params that should go with the request.
				Standard params (api key, format, etc.) not needed.

		Raises:
			CVRateLimitReached: The CV rate limit for this endpoint has been reached
			InvalidComicVineApiKey: The CV api key is not valid
			VolumeNotMatched: The volume with the given ID is not found

		Returns:
			dict: The raw API response
		"""
		if not url_path.endswith('/'):
			url_path += '/'

		try:
			result = self.ssn.get(
				f'{self.api_url}{url_path}',
				params=params
			).json()

		except (JSONDecodeError, requests_ConnectionError):
			raise CVRateLimitReached

		if result['status_code'] == 100:
			raise InvalidComicVineApiKey
		elif result['status_code'] == 101:
			raise VolumeNotMatched
		elif result['status_code'] == 107:
			raise CVRateLimitReached

		return result

	async def __call_api_async(self,
		session: ClientSession,
		url_path: str,
		params: dict,
		default: Union[T, None] = None
	) -> Union[Dict[str, Any], T]:
		"""Make an CV API call asynchronously (with error handling).

		Args:
			session (ClientSession): The aiohttp session to make the request with.

			url_path (str): The path of the url to make the call to (e.g. '/volumes').
				Beginning '/' required.

			params (dict): The URL params that should go with the request.
				Standard params (api key, format, etc.) not needed.

			default (Union[T, None], optional): Return value in case of error
			instead of raising error.
				Defaults to None.

		Raises:
			CVRateLimitReached: The CV rate limit for this endpoint has been reached,
			and no 'default' was supplied.

		Returns:
			Union[Dict[str, Any], T]: The raw API response or the value of 'default' on error.
		"""
		if not url_path.endswith('/'):
			url_path += '/'

		try:
			async with session.get(
				f'{self.api_url}{url_path}',
				params={**self._params, **params},
				headers=self._headers
			) as response:
				result: Dict[str, Any] = await response.json()

		except (ContentTypeError, requests_ConnectionError):
			if default is not None:
				return default
			raise CVRateLimitReached

		if result['status_code'] == 107:
			if default is not None:
				return default
			raise CVRateLimitReached

		return result

	def test_token(self) -> bool:
		"""Test if the token works

		Returns:
			bool: Whether or not the token works.
		"""
		try:
			self.__call_api(
				'/publisher/4010-31',
				{'field_list': 'id'}
			)

		except (CVRateLimitReached,
		  		InvalidComicVineApiKey):
			return False

		return True

	def __format_volume_output(self, volume_data: dict) -> dict:
		"""Format the ComicVine API output containing the info
		about the volume to the "Kapowarr format"

		Args:
			volume_data (dict): The ComicVine API output

		Returns:
			dict: The formatted version
		"""
		result = {
			'comicvine_id': int(volume_data['id']),

			'title': normalize_string(volume_data['name'].strip()),
			'year': None,
			'volume_number': 1,
			'cover': volume_data['image']['small_url'],

			'description': _clean_description(volume_data['description']),
			'aliases': [],
			'comicvine_info': volume_data.get('site_detail_url'),

			'publisher': (volume_data.get('publisher') or {}).get('name'),
			'issue_count': int(volume_data['count_of_issues'])
		}

		if volume_data['start_year'] is not None:
			y: str = volume_data['start_year']

			if '/' in y:
				y = next(
					(e for e in y.split('/') if len(e) == 4),
					None
				)

			if y:
				y = (y
					.replace('-', '0')
					.replace('?', '')
				)

			if y and y.isdigit():
				result['year'] = int(y)

		volume_result = volume_regex.search(volume_data['deck'] or '')
		if volume_result:
			result['volume_number'] = convert_volume_number_to_int(
				volume_result.group(1)
			)

		translation_result = translation_regex.match(
			volume_data['description'] or ''
		)
		result['translated'] = translation_result is not None

		# Turn aliases from string into list
		if volume_data.get('aliases'):
			result['aliases'] = volume_data['aliases'].split('\r\n')

		return result

	def __format_issue_output(self, issue_data: dict) -> dict:
		"""Format the ComicVine API output containing the info
		about the issue to the "Kapowarr format"

		Args:
			issue_data (dict): The ComicVine API output

		Returns:
			dict: The formatted version
		"""
		result = {
			'comicvine_id': issue_data['id'],
			'volume_id': int(issue_data['volume']['id']),
			'issue_number': issue_data['issue_number'],
			'calculated_issue_number': process_issue_number(
				issue_data['issue_number']
			),
			'title': issue_data['name'] or None,
			'date': issue_data['cover_date'] or None,
			'description': _clean_description(
				issue_data['description'],
				short=True
			)
		}
		return result

	async def fetch_volume_async(self, id: str) -> dict:
		"""Get the metadata of a volume from ComicVine async,
		formatted to the "Kapowarr format".

		Args:
			id (str): The comicvine id of the volume.
				The `4050-` prefix is optional.

		Raises:
			VolumeNotMatched: No volume found with given ID in CV DB
			CVRateLimitReached: The ComicVine rate limit is reached

		Returns:
			dict: The metadata of the volume
		"""
		id = self.__normalize_cv_id(id)
		LOGGER.debug(f'Fetching volume data for {id}')

		async with ClientSession() as session:
			result = await self.__call_api_async(
				session,
				f'/volume/{id}',
				{'field_list': self.volume_field_list}
			)

			volume_info = self.__format_volume_output(result['results'])
			volume_info['cover'] = await self.__call_request_async(
				session,
				volume_info['cover']
			)

			LOGGER.debug(f'Fetching issue data for volume {id}')
			volume_info['issues'] = await self.fetch_issues_async([
				id.split('-')[-1]
			])

			LOGGER.debug(f'Fetching volume data result: {volume_info}')
			return volume_info

	async def fetch_volumes_async(self, ids: List[str]) -> List[dict]:
		"""Get the metadata of the volumes given from ComicVine async,
		formatted to the "Kapowarr format".

		Args:
			ids (List[str]): The comicvine ids of the volumes.
				The `4050-` prefix should not be included.

		Returns:
			List[dict]: The metadata of the volumes
		"""
		LOGGER.debug(f'Fetching volume data for {ids}')

		volume_infos = []
		async with ClientSession() as session:
			# 10 requests of 100 vol per round
			for request_batch in batched(ids, 1000):
				tasks = [
					create_task(self.__call_api_async(
						session,
						'/volumes',
						{'field_list': self.volume_field_list,
						'filter': f'id:{"|".join(id_batch)}'},
						{'results': []}
					))
					for id_batch in batched(request_batch, 100)
				]
				responses = await gather(*tasks)

				# cover_tasks = []
				# cover_ids = []
				cover_map = {}
				for batch in responses:
					for result in batch['results']:
						volume_info = self.__format_volume_output(result)
						volume_infos.append(volume_info)
						cover_map[volume_info['comicvine_id']] = create_task(
							self.__call_request_async(
								session,
								volume_info['cover']
							)
						)

				cover_responses = dict(zip(
					cover_map.keys(),
					await gather(*cover_map.values())
				))
				for vi in volume_infos:
					vi['cover'] = cover_responses.get(vi['comicvine_id'])

			return volume_infos

	async def fetch_issues_async(self, ids: List[str]) -> List[dict]:
		"""Get the metadata of the issues of volumes given from ComicVine async,
		formatted to the "Kapowarr format".

		Args:
			ids (List[str]): The comicvine ids of the volumes.
				The `4050-` prefix should not be included.

		Returns:
			List[dict]: The metadata of all the issues inside the volumes
		"""
		LOGGER.debug(f'Fetching issue data for volumes {ids}')

		issue_infos = []
		async with ClientSession() as session:
			for id_batch in batched(ids, 50):
				try:
					results = self.__call_api(
						'/issues',
						{'field_list': self.issue_field_list,
						'filter': f'volume:{"|".join(id_batch)}'}
					)
				except CVRateLimitReached:
					break

				issue_infos += [
					self.__format_issue_output(r)
					for r in results['results']
				]

				if results['number_of_total_results'] > 100:
					for offset_batch in batched(
						range(100, results['number_of_total_results'], 100),
						10
					):
						tasks = [
							create_task(self.__call_api_async(
								session,
								'/issues',
								{'field_list': self.issue_field_list,
								'filter': f'volume:{"|".join(id_batch)}',
								'offset': offset},
								{'results': []}
							))
							for offset in offset_batch
						]
						responses = await gather(*tasks)

						for batch in responses:
							issue_infos += [
								self.__format_issue_output(r)
								for r in batch['results']
							]
			return issue_infos

	def __process_search_results(self,
		query: str,
		results: List[dict]
	) -> List[dict]:
		"""Format the search results from `self.search_volumes()`
		or `self.search_volumes_async()`

		Args:
			query (str): The processed query that was used
			results (List[dict]): The unformatted search results

		Returns:
			List[dict]: The formatted search results
		"""
		cursor = get_db()

		results = [self.__format_volume_output(r) for r in results]

		# Mark entries that are already added
		volume_ids: Dict[int, int] = dict(cursor.execute(f"""
			SELECT comicvine_id, id
			FROM volumes
			WHERE {' OR '.join('comicvine_id = ' + str(r['comicvine_id']) for r in results)}
			LIMIT 50;
		"""))
		for result in results:
			result.update({
				'already_added': volume_ids.get(result['comicvine_id'])
			})

		# Sort results (prefer direct title matches and then sort those on volume number)
		results.sort(
			key=lambda v: (
				int(not v['title'] == query),
				(
					v['volume_number']
					or
					float('inf') if v['title'] == query else float('inf') + 1
				)
			)
		)

		LOGGER.debug(f'Searching for volumes with query result: {results}')
		return results

	def search_volumes(self, query: str) -> List[dict]:
		"""Search for volumes in the ComicVine database

		Args:
			query (str): The query to use when searching

		Returns:
			List[dict]: A list with search results
		"""
		LOGGER.debug(f'Searching for volumes with the query {query}')

		if query.startswith('4050-') or query.startswith('cv:'):
			query = self.__normalize_cv_id(query)
			if not query:
				return []

			results: List[dict] = [self.__call_api(
				f'/volume/{query}',
				{'field_list': self.search_field_list}
			)['results']]
			if results == [[]]:
				return []
		else:
			results: List[dict] = self.__call_api(
				'/search',
				{'query': query,
				'resources': 'volume',
				'limit': 50,
				'field_list': self.search_field_list}
			)['results']
			if not results:
				return []

		return self.__process_search_results(query, results)

	async def search_volumes_async(self,
		session: ClientSession,
		query: str
	) -> List[dict]:
		"""Search for volumes in the ComicVine database asynchronously

		Args:
			session (ClientSession): An aiohttp client session for the requests
			query (str): The query to use when searching

		Returns:
			List[dict]: A list with search results
		"""
		LOGGER.debug(f'Searching for volumes with the query {query}')

		if query.startswith('4050-') or query.startswith('cv:'):
			query = self.__normalize_cv_id(query)
			if not query:
				return []

			try:
				results: List[dict] = [(await self.__call_api_async(
					session,
					f'/volume/{query}',
					{'field_list': self.search_field_list}
				))['results']]

			except CVRateLimitReached:
				return []

			if results == [[]]:
				return []

		else:
			try:
				results: List[dict] = (await self.__call_api_async(
					session,
					'/search',
					{'query': query,
					'resources': 'volume',
					'limit': 50,
					'field_list': self.search_field_list}
				))['results']

			except CVRateLimitReached:
				return []

			if not results:
				return []

		return self.__process_search_results(query, results)
