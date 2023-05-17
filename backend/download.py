#-*- coding: utf-8 -*-

"""This file contains functions regarding directly downloading content from getcomics.org
"""

import logging
from abc import ABC, abstractmethod
from hashlib import sha1
from os import listdir, remove
from os.path import basename, join, splitext
from re import IGNORECASE, compile
from threading import Thread
from time import perf_counter
from typing import Dict, List, Tuple, Union

from bencoding import bdecode, bencode
from bs4 import BeautifulSoup
from requests import get
from requests.exceptions import ConnectionError as requests_ConnectionError

from backend.blocklist import add_to_blocklist, blocklist_contains
from backend.credentials import Credentials
from backend.custom_exceptions import (DownloadLimitReached, DownloadNotFound,
                                       LinkBroken)
from backend.db import get_db
from backend.files import extract_filename_data
from backend.naming import (generate_issue_name, generate_issue_range_name,
                            generate_tpb_name)
from backend.post_processing import PostProcessing
from backend.search import _check_matching_titles
from backend.settings import (Settings, blocklist_reasons, private_settings,
                              supported_source_strings)

from .lib.mega import Mega, RequestError, sids

file_extension_regex = compile(r'(?<=\.)[\w\d]{2,4}(?=$|;|\s)|(?<=\/)[\w\d]{2,4}(?=$|;|\s)', IGNORECASE)
mega_regex = compile(r'https?://mega\.(nz|io)/(#(F\!|\!)|folder/|file/)', IGNORECASE)
mediafire_regex = compile(r'https?://www\.mediafire\.com/', IGNORECASE)

download_chunk_size = 4194304 # 4MB Chunks
credentials = Credentials(sids)

#=====================
# Download implementations
#=====================
QUEUED_STATE = 'queued'
DOWNLOADING_STATE = 'downloading'
IMPORTING_STATE = 'importing'
FAILED_STATE = 'failed'
CANCELED_STATE = 'canceled'

class Download(ABC):
	id: int
	original_link: str
	title: str
	state: str
	progress: float
	speed: float
	link: int
	file: str
	source: str

	@abstractmethod
	def run(self) -> None:
		return
		
	@abstractmethod
	def stop(self) -> None:
		return

class BaseDownload(Download):
	def __init__(self):
		self.state: str = QUEUED_STATE

class DirectDownload(BaseDownload):
	"""For downloading a file directly from a link
	"""	
	def __init__(self, link: str, filename_body: str, source: str):
		"""Setup the direct download

		Args:
			link (str): The link (that leads to a file) that should be used
			filename_body (str): The body of the filename to write to
			source (str): The name of the source of the link

		Raises:
			LinkBroken: The link doesn't work
		"""
		logging.debug(f'Creating download: {link}, {filename_body}')
		super().__init__()
		self.progress: float = 0.0
		self.speed: float = 0.0
		self.link = link
		self.source = source

		self.size: int = 0
		r = get(self.link, stream=True)
		r.close()
		if not r.ok:
			raise LinkBroken(1, blocklist_reasons[1])
		self.__filename_body = filename_body.rstrip('.')

		self.file = self.__build_filename(r)
		self.title = splitext(basename(self.file))[0]
		self.size = int(r.headers.get('content-length',-1))

	def __extract_extension(self, content_type: str, content_disposition: str, url: str) -> str:
		"""Find the extension of the file behind the link

		Args:
			content_type (str): The value of the Content-Type header
			content_disposition (str): The value of the Content-Disposition header
			url (str): The url leading to the file

		Returns:
			str: The extension of the file, including the `.`
		"""		
		match = file_extension_regex.findall(
			' '.join((
				content_type,
				content_disposition,
				url
			))
		)
		if match:
			extension = '.' + match[0]
		else:
			extension = ''

		return extension

	def __build_filename(self, r) -> str:
		"""Build the filename from the download folder, filename body and extension

		Args:
			r (_type_): The request to the link

		Returns:
			str: The filename
		"""		
		folder = Settings().get_settings()['download_folder']
		extension = self.__extract_extension(
			r.headers.get('Content-Type', ''),
			r.headers.get('Content-Disposition', ''),
			r.url
		)
		return join(folder, self.__filename_body + extension)

	def run(self) -> None:
		"""Start the download
		"""		
		self.state = DOWNLOADING_STATE
		size_downloaded = 0

		with get(self.link, stream=True) as r:
			with open(self.file, 'wb') as f:
				start_time = perf_counter()
				for chunk in r.iter_content(chunk_size=download_chunk_size):
					if self.state == CANCELED_STATE:
						break

					f.write(chunk)

					# Update progress
					chunk_size = len(chunk)
					size_downloaded += chunk_size
					self.speed = round(chunk_size / (perf_counter() - start_time), 2)
					if self.size == -1:
						# Total size of file is not given so set progress to amount downloaded
						self.progress = size_downloaded
					else:
						# Total size of file is given so calculate progress and speed
						self.progress = round(size_downloaded / self.size * 100, 2)
					start_time = perf_counter()

		return

	def stop(self) -> None:
		"""Interrupt the download
		"""
		self.state = CANCELED_STATE
		return

class MegaDownload(BaseDownload):
	@property
	def progress(self) -> float:
		return self._mega.progress

	@property
	def speed(self) -> float:
		return self._mega.speed

	@property
	def size(self) -> int:
		return self._mega.size

	def __init__(self, link: str, filename_body: str, source: str='mega'):
		"""Setup the mega download

		Args:
			link (str): The mega link
			filename_body (str): The body of the filename to write to

		Raises:
			LinkBroken: The link doesn't work
		"""
		logging.debug(f'Creating mega download: {link}, {filename_body}')
		super().__init__()
		self.link = link
		self.source = source

		self.__filename_body = filename_body.rstrip('.')
		cred = credentials.get_one_from_source('mega')
		try:
			self._mega = Mega(link, cred['email'], cred['password'])
		except RequestError:
			raise LinkBroken(1, blocklist_reasons[1])

		self.file = self.__build_filename()
		self.title = splitext(basename(self.file))[0]
		
	def __extract_extension(self) -> str:
		"""Find the extension of the file behind the link

		Returns:
			str: The extension of the file, including the `.`
		"""
		return splitext(self._mega.mega_filename)[1]

	def __build_filename(self) -> str:
		"""Build the filename from the download folder, filename body and extension

		Returns:
			str: The filename
		"""
		folder = Settings().get_settings()['download_folder']
		extension = self.__extract_extension()
		return join(folder, self.__filename_body + extension)

	def run(self) -> None:
		"""Start the download
		"""		
		self.state = DOWNLOADING_STATE
		self._mega.download_url(self.file)

	def stop(self) -> None:
		"""Interrupt the download
		"""		
		self.state = CANCELED_STATE
		self._mega.downloading = False

#=====================
# Download link analysation
#=====================
def _check_download_link(link_text: str, link: str) -> Union[str, None]:
	"""Check if download link is supported and allowed

	Args:
		link_text (str): The title of the link
		link (str): The link itself

	Returns:
		Union[str, None]: Either the name of the service (e.g. `mega`) or `None` if it's not allowed
	"""	
	logging.debug(f'Checking download link: {link}, {link_text}')
	if not link:
		return

	# Check if link is in blocklist
	if blocklist_contains(link):
		return

	# Check if link is from supported source
	for source in supported_source_strings:
		if link_text in source:
			logging.debug(f'Checking download link: {link_text} maps to {source[0]}')
			return source[0]

	return

def _purify_link(link: str) -> dict:
	"""Extract the link that directly leads to the download from the link on the getcomics page

	Args:
		link (str): The link on the getcomics page

	Raises:
		LinkBroken: Link is invalid, not supported or broken

	Returns:
		dict: The pure link, a download instance for the correct service (e.g. DirectDownload or MegaDownload) and the source title
	"""
	logging.debug(f'Purifying link: {link}')
	# Go through every link and get it all down to direct download or magnet links
	if link.startswith('magnet:?'):
		# Link is already magnet link
		raise LinkBroken(2, blocklist_reasons[2])

	elif link.startswith('http'):
		r = get(link, headers={'User-Agent': 'Kapowarr'}, stream=True)
		r.close()
		url = r.url
		
		if mega_regex.search(url):
			# Link is mega
			if not '#F!' in url and not '/folder/' in url:
				return {'link': url, 'target': MegaDownload, 'source': 'mega'}
			# else
			# Link is not supported (folder most likely)
			raise LinkBroken(2, blocklist_reasons[2])
		
		elif mediafire_regex.search(url):
			# Link is mediafire
			if 'error.php' in url:
				# Link is broken
				raise LinkBroken(1, blocklist_reasons[1])
			
			elif '/folder/' in url:
				# Link is not supported (folder most likely)
				raise LinkBroken(2, blocklist_reasons[2])
			
			soup = BeautifulSoup(r.text, 'html.parser')
			button = soup.find('a', {'id': 'downloadButton'})
			if button:
				return {'link': button['href'], 'target': DirectDownload, 'source': 'mediafire'}

			# Link is not broken and not a folder but we still can't find the download button...
			raise LinkBroken(1, blocklist_reasons[1])

		elif url.startswith('magnet:?'):
			# Link is magnet link
			raise LinkBroken(2, blocklist_reasons[2])
			return {'link': url, 'target': None, 'source': 'torrent'}

		elif r.headers.get('Content-Type','') == 'application/x-bittorrent':
			# Link is torrent file
			raise LinkBroken(2, blocklist_reasons[2])
			hash = sha1(bencode(bdecode(r.content)[b"info"])).hexdigest()
			return {'link': "magnet:?xt=urn:btih:" + hash + "&tr=udp://tracker.cyberia.is:6969/announce&tr=udp://tracker.port443.xyz:6969/announce&tr=http://tracker3.itzmx.com:6961/announce&tr=udp://tracker.moeking.me:6969/announce&tr=http://vps02.net.orel.ru:80/announce&tr=http://tracker.openzim.org:80/announce&tr=udp://tracker.skynetcloud.tk:6969/announce&tr=https://1.tracker.eu.org:443/announce&tr=https://3.tracker.eu.org:443/announce&tr=http://re-tracker.uz:80/announce&tr=https://tracker.parrotsec.org:443/announce&tr=udp://explodie.org:6969/announce&tr=udp://tracker.filemail.com:6969/announce&tr=udp://tracker.nyaa.uk:6969/announce&tr=udp://retracker.netbynet.ru:2710/announce&tr=http://tracker.gbitt.info:80/announce&tr=http://tracker2.dler.org:80/announce",
						'target': None}

		# Link is direct download from getcomics ('Main Server', 'Mirror Server', 'Link 1', 'Link 2', etc.)
		return {'link': url, 'target': DirectDownload, 'source': 'getcomics'}

	else:
		raise LinkBroken(2, blocklist_reasons[2])

link_filter_1 = lambda e: e.name == 'p' and 'Language' in e.text and e.find('p') is None
link_filter_2 = lambda e: e.name == 'li' and e.parent.name == 'ul' and ((0 < e.text.count('|') == len(e.find_all('a')) - 1) or (e.find('a') and _check_download_link(e.find('a').text.strip().lower(), e.find('a').attrs.get('href'))))
def _extract_get_comics_links(
	soup: BeautifulSoup
) -> Dict[str, Dict[str, List[str]]]:
	"""Go through the getcomics page and extract all download links.
	The links are grouped. All links in a group lead to the same download, only via different services (mega, direct download, mirror download, etc.)

	Args:
		soup (BeautifulSoup): The soup of the getcomics page

	Returns:
		Dict[str, Dict[str, List[str]]]: The outer dict maps the group name to the group.
		The group is a dict that maps each service in the group to a list of links for that service.
		Example:
			{
				'Amazing Spider-Man V1 Issue 1-10': {
					'mega': ['https://mega.io/abc'],
					'direct': ['https://main.server.com/abc', 'https://mirror.server.com/abc']
				},
				'Amazing Spider-Man V1 Issue 11-20': {...}
			}
	"""
	logging.debug('Extracting download groups')
	download_groups = {}
	body = soup.find('article', {'class': 'post-body'})
	for result in body.find_all(link_filter_1):
		group_title: str = result.get_text('\x00').partition('\x00')[0]
		if 'variant cover' in group_title.lower():
			continue
		group_links = {}
		for e in result.next_sibling.next_elements:
			if e.name == 'hr':
				break
			elif e.name == 'div' and 'aio-button-center' in (e.attrs.get('class', [])):
				group_link = e.find('a')
				link_title = group_link.text.strip().lower()
				match = _check_download_link(link_title, group_link['href'])
				if match:
					group_links.setdefault(match, []).append(group_link['href'])
		if group_links:
			download_groups.update({group_title: group_links})

	for result in body.find_all(link_filter_2):
		group_title: str = result.get_text('\x00').partition('\x00')[0]
		if 'variant cover' in group_title.lower():
			continue
		group_links = {}
		for group_link in result.find_all('a'):
			link_title = group_link.text.strip().lower()
			match = _check_download_link(link_title, group_link['href'])
			if match:
				group_links.setdefault(match, []).append(group_link['href'])
		if group_links:
			download_groups.update({group_title: group_links})

	logging.debug(f'Download groups: {download_groups}')
	return download_groups

def _sort_link_paths(p: List[dict]) -> int:
	"""Sort the link paths. TPB's are sorted highest, then from most downloads to least.

	Args:
		p (List[dict]): A link path

	Returns:
		int: The rating (lower is better)
	"""	
	if p[0]['info']['special_version']:
		return 0
	return 1 / len(p)
	
def _process_extracted_get_comics_links(
	download_groups: Dict[str, Dict[str, List[str]]],
	volume_title: str,
	volume_number: int
) -> List[List[Dict[str, dict]]]:
	"""Based on the download groups, find different "paths" to download the most amount of content.
	On the same page, there might be a download for `TPB + Extra's`, `TPB`, `Issue A-B` and for `Issue C-D`.
	This function creates "paths" that contain links that together download as much content without overlapping.
	So a path would be created for `TPB + Extra's`. A second path would be created for `TPB` and a third path for
	`Issue A-B` + `Issue C-D`. Paths 2 and on are basically backup options for if path 1 doesn't work, to still get
	the most content out of the page.

	Args:
		download_groups (Dict[str, Dict[str, List[str]]]): The download groups (output of download._extract_get_comics_links())
		volume_title (str): The name of the volume
		volume_number (int): The volume number

	Returns:
		List[List[Dict[str, dict]]]: The list contains all paths. Each path is a list of download groups. The `info` key has
		as it's value the output of files.extract_filename_data() for the title of the group. The `links` key contains the
		download links grouped together with their service.
	"""	
	logging.debug('Creating link paths')
	annual = 'annual' in volume_title.lower()
	service_preference_order = dict((v, k) for k, v in enumerate(Settings().get_service_preference()))
	link_paths: List[List[dict]] = []
	for desc, sources in download_groups.items():
		processed_desc = extract_filename_data(desc, assume_volume_number=False)
		if (_check_matching_titles(volume_title, processed_desc['series'])
		and (processed_desc['volume_number'] is None
			or
			processed_desc['volume_number'] == volume_number)
		and (processed_desc['special_version'] or processed_desc['issue_number'])
		and processed_desc['annual'] == annual
		):
			# Group matches/contains what is desired to be downloaded
			sources = {s: sources[s] for s in sorted(sources, key=lambda k: service_preference_order[k])}
			if processed_desc['special_version']:
				link_paths.append([{'info': processed_desc, 'links': sources}])
			else:
				# Find path with ranges and single issues that doesn't have a link that already covers this one
				for path in link_paths:
					for entry in path:
						if entry['info']['special_version']:
							break
						if isinstance(entry['info']['issue_number'], float):
							if isinstance(processed_desc['issue_number'], float):
								if entry['info']['issue_number'] == processed_desc['issue_number']:
									break
							else:
								if processed_desc['issue_number'][0] <= entry['info']['issue_number'] <= processed_desc['issue_number'][1]:
									break
						else:
							if isinstance(processed_desc['issue_number'], float):
								if entry['info']['issue_number'][0] <= processed_desc['issue_number'] <= entry['info']['issue_number'][1]:
									break
							else:
								if (entry['info']['issue_number'][0] <= processed_desc['issue_number'][0] <= entry['info']['issue_number'][1]
									or entry['info']['issue_number'][0] <= processed_desc['issue_number'][1] <= entry['info']['issue_number'][1]):
									break
					else:
						path.append({'info': processed_desc, 'links': sources})
						break
				else:
					link_paths.append([{'info': processed_desc, 'links': sources}])
	
	link_paths.sort(key=_sort_link_paths)

	logging.debug(f'Link paths: {link_paths}')
	return link_paths

def _test_paths(
	link_paths: List[List[Dict[str, dict]]],
	volume_id: int
) -> Tuple[List[dict], bool]:
	"""Test the links of the paths and determine based on which links work which path to go for

	Args:
		link_paths (List[List[Dict[str, dict]]]): The link paths (output of download._process_extracted_get_comics_links())
		volume_id (int): The id of the volume

	Returns:
		Tuple[List[dict], bool]: A list of downloads and wether or not the download limit for a service on the page is reached.

		If the list is empty and the bool is False, the page doesn't have any working links and can be blacklisted.

		If the list is empty and the bool is True, the page has working links but the service of the links has reached it's download limit, so nothing on the page can be downloaded.
		However, the page shouldn't be blacklisted because the links _are_ working.
		
		If the list has content, the page has working links that can be used.
	"""
	logging.debug('Testing paths')
	limit_reached = False
	downloads = []
	for path in link_paths:
		for download in path:
			# Generate name
			if download['info']['special_version']:
				# Link for TPB
				name = generate_tpb_name(volume_id)

			elif isinstance(download['info']['issue_number'], tuple):
				# Link for issue range
				name = generate_issue_range_name(
					volume_id,
					*download['info']['issue_number']
				)
			
			else:
				# Link for single issue
				name = generate_issue_name(volume_id, download['info']['issue_number'])

			# Find working link
			for links in download['links'].values():
				for link in links:
					try:
						# Maybe make purify link async so that all links can be purified 'at the same time'?
						# https://www.youtube.com/watch?v=nFn4_nA_yk8&t=1053s
						# https://stackoverflow.com/questions/53336675/get-aiohttp-results-as-string
						pure_link = _purify_link(link)
						dl_instance = pure_link['target'](link=pure_link['link'], filename_body=name, source=pure_link['source'])
					except LinkBroken as lb:
						# Link is broken
						add_to_blocklist(link, lb.reason_id)
					except DownloadLimitReached:
						# Link works but the download limit for the service is reached
						limit_reached = True
					else:
						downloads.append({'name': name, 'link': link, 'instance': dl_instance})
						break
				else:
					continue
				break
			else:
				# No working link found in group
				if download['info']['special_version']:
					# Download is essential for group and it doesn't work so try next path
					break
				else:
					continue
		else:
			break
		downloads = []
	
	logging.debug(f'Chosen links: {downloads}')
	return downloads, limit_reached
		
def _extract_download_links(link: str, volume_id: int, issue_id: int=None) -> Tuple[List[dict], bool]:
	"""Filter, select and setup downloads from a getcomic page

	Args:
		link (str): Link to the getcomics page
		volume_id (int): The id of the volume for which the getcomics page is
		issue_id (int, optional): The id of the issue for which the getcomics page is. Defaults to None.

	Returns:
		Tuple[List[dict], bool]: List of downloads and wether or not the download limit for a service on the page is reached.

		If the list is empty and the bool is False, the page doesn't have any working links and can be blacklisted.

		If the list is empty and the bool is True, the page has working links but the service of the links has reached it's download limit, so nothing on the page can be downloaded.
		However, the page shouldn't be blacklisted because the links _are_ working.
		
		If the list has content, the page has working links that can be used.
	"""	
	logging.debug(f'Extracting download links from {link} for volume {volume_id} and issue {issue_id}')

	try:
		r = get(link, headers={'user-agent': 'Kapowarr'}, stream=True)
		if not r.ok:
			raise requests_ConnectionError
	except requests_ConnectionError:
		# Link broken
		add_to_blocklist(link, 1)

	if link.startswith(private_settings['getcomics_url']) and not link.startswith(private_settings['getcomics_url'] + '/links/'):
		# Link is to a getcomics page

		# Get info of volume
		volume_info = get_db('dict').execute(
			"SELECT title, volume_number FROM volumes WHERE id = ? LIMIT 1",
			(volume_id,)
		).fetchone()

		soup = BeautifulSoup(r.text, 'html.parser')

		# Extract the download groups and filter invalid links
		# {"Group Title": {"source1": ["link1"]}}
		download_groups = _extract_get_comics_links(soup)

		# Filter incorrect download groups and combine them (or not) to create download paths
		# [[{'info': {}, 'links': {}}, {'info': {}, 'links': {}}], [{'info': {}, 'links': {}}]]
		link_paths = _process_extracted_get_comics_links(download_groups, volume_info['title'], volume_info['volume_number'])

		# Decide which path to take by testing the links
		# [{'name': 'Filename', 'link': 'link_on_getcomics_page', 'instance': Download_instance}]
		return _test_paths(link_paths, volume_id)

	#else
	# Link is a torrent file or magnet link

	return [], False

#=====================
# Download handling
#=====================
class DownloadHandler:
	"""Handles downloads
	"""	
	queue: List[dict] = []
	
	def __init__(self, context) -> None:
		"""Setup the download handler

		Args:
			context (Flask): A flask app instance
		"""		
		self.context = context.app_context
		return

	def __run_download(self, download: dict) -> None:
		"""Start a download. Intended to be run in a thread.

		Args:
			download (dict): The download to run. One of the entries in self.queue.
		"""	
		logging.info(f'Starting download: {download["id"]}')
		
		with self.context():
			download['instance'].run()
			
			if download['instance'].state == CANCELED_STATE:
				PostProcessing(download, self.queue).short()
				return
			# else
			download['instance'].state = IMPORTING_STATE
			PostProcessing(download, self.queue).full()
			
			self.queue.pop(0)
			self._process_queue()
			return

	def _process_queue(self) -> None:
		"""Handle the queue. In the case that there is something in the queue and it isn't already downloading,
		start the download. This can safely be called multiple times while a download is going or while there is
		nothing in the queue.
		"""	
		if not self.queue:
			return
		
		first_entry = self.queue[0]
		if first_entry['instance'].state == QUEUED_STATE:
			first_entry['thread'].start()
		return

	def __format_entry(self, d: dict) -> dict:
		"""Format a queue entry for API response.

		Args:
			d (dict): The queue entry

		Returns:
			dict: The formatted version
		"""		
		return {
			'id': d['id'],
			'status': d['instance'].state,
			'link': d['instance'].link,
			'original_link': d['original_link'],
			'source': d['instance'].source,
			'file': d['instance'].file,
			'size': d['instance'].size,
			'title': d['instance'].title,
			'progress': d['instance'].progress,
			'speed': d['instance'].speed,
			'volume_id': d['volume_id'],
			'issue_id': d['issue_id']
		}

	def load_downloads(self) -> None:
		"""Load downloads from the database and add them to the queue for re-downloading
		"""		
		logging.debug('Loading downloads from database')
		with self.context():
			cursor2 = get_db('dict', temp=True)
			cursor2.execute("""
				SELECT
					id,
					link,
					volume_id, issue_id
				FROM download_queue;
			""")
			cursor = get_db()
			for download in cursor2:
				logging.debug(f'Download from database: {dict(download)}')
				self.add(download['link'], download['volume_id'], download['issue_id'], download['id'])
				cursor.connection.commit()
		return

	def add(self,
		link: str,
		volume_id: int, issue_id: int=None,
		_download_db_id_override: int=None
	) -> List[dict]:
		"""Add a download to the queue

		Args:
			link (str): A getcomics link to download from
			volume_id (int): The id of the volume for which the download is intended
			issue_id (int, optional): The id of the issue for which the download is intended. Defaults to None.
			_download_db_id_override (int, optional): Internal use only. Don't use. Defaults to None.

		Returns:
			List[dict]: Queue entries that were added from the link.
		"""		
		logging.info(
			f'Adding download for volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: {link}'
		)
		
		# Extract download links and convert into Download instances
		# [{'name': 'Filename', 'link': 'link_on_getcomics_page', 'instance': Download_instance}]
		downloads, limit_reached = _extract_download_links(link, volume_id, issue_id)
		if not downloads:
			if not limit_reached:
				# No links extracted from page so add it to blocklist
				add_to_blocklist(link, 3)
			logging.warning('Unable to extract download links from source')
			if _download_db_id_override:
				with self.context():
					get_db().execute(
						"DELETE FROM download_queue WHERE id = ?",
						(_download_db_id_override,)
					)
			return []

		result = []
		with self.context():
			# Register download in database
			if _download_db_id_override is None:
				db_id = get_db().execute("""
					INSERT INTO download_queue(link, volume_id, issue_id)
					VALUES (?,?,?);
					""",
					(link, volume_id, issue_id)
				).lastrowid
			else:
				db_id = _download_db_id_override

			for download in downloads:
				download['original_link'] = link
				download['volume_id'] = volume_id
				download['issue_id'] = issue_id
				download['id'] = self.queue[-1]['id'] + 1 if self.queue else 1
				download['db_id'] = db_id
				download['thread'] = Thread(target=self.__run_download, args=(download,), name="Download Handler")

				# Add to queue
				result.append(self.__format_entry(download))
				self.queue.append(download)

		self._process_queue()
		return result

	def stop_handle(self) -> None:
		"""Cancel any running download and stop the handler
		"""		
		logging.debug('Stopping download thread')
		if self.queue:
			self.queue[0]['instance'].stop()
			self.queue[0]['thread'].join()
		return

	def get_all(self) -> List[dict]:
		"""Get all queue entries

		Returns:
			List[dict]: All queue entries, formatted after self.__format_entry()
		"""		
		result = list(map(
			self.__format_entry,
			self.queue
		))
		return result
	
	def get_one(self, download_id: int) -> dict:
		"""Get a queue entry based on it's id.

		Args:
			download_id (int): The id of the download to fetch

		Raises:
			DownloadNotFound: The id doesn't map to any download in the queue

		Returns:
			dict: The queue entry, formatted after self.__format_entry()
		"""		
		for entry in self.queue:
			if entry['id'] == download_id:
				return self.__format_entry(entry)
		raise DownloadNotFound
	
	def remove(self, download_id: int) -> None:
		"""Remove a download entry from the queue

		Args:
			download_id (int): The id of the download to remove from the queue

		Raises:
			DownloadNotFound: The id doesn't map to any download in the queue
		"""	
		logging.info(f'Removing download with id {download_id}')

		# Delete download from queue
		for download in self.queue:
			if download['id'] == download_id:
				if download['instance'].state == DOWNLOADING_STATE:
					download['instance'].stop()
					download['thread'].join()
				self.queue.remove(download)
				PostProcessing(download, self.queue)._remove_from_queue()
				break
		else:
			raise DownloadNotFound

		self._process_queue()
		return
	
	def empty_download_folder(self) -> None:
		"""Empty the temporary download folder of files that aren't being downloaded.
		Handy in the case that a crash left half-downloaded files behind in the folder.
		"""
		logging.info(f'Emptying the temporary download folder')
		folder = Settings().get_settings()['download_folder']
		files_in_queue = [basename(download['instance'].file) for download in self.queue]
		files_in_folder = listdir(folder)
		ghost_files = [join(folder, f) for f in files_in_folder if not f in files_in_queue]
		for f in ghost_files:
			remove(f)
		return

#=====================
# Download History Managing
#=====================
def get_download_history(offset: int=0) -> List[dict]:
	"""Get the download history in blocks of 50.

	Args:
		offset (int, optional): The offset of the list. The higher the number, the deeper into history you go. Defaults to 0.

	Returns:
		List[dict]: The history entries.
	"""	
	result = list(map(
		dict,
		get_db('dict').execute(
			"""
			SELECT
				original_link, title, downloaded_at
			FROM download_history
			ORDER BY downloaded_at DESC
			LIMIT 50
			OFFSET ?;
			""",
			(offset * 50,)
		)
	))
	return result

def delete_download_history() -> None:
	"""Delete complete download history
	"""
	logging.info('Deleting download history')
	get_db().execute("DELETE FROM download_history;")
	return
