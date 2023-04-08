#-*- coding: utf-8 -*-

"""This file contains functions regarding directly downloading content from getcomics.org
"""

import logging
from abc import ABC, abstractmethod
from hashlib import sha1
from os.path import basename, join, splitext
from re import IGNORECASE, compile
from threading import Thread
from time import perf_counter
from typing import Dict, List, Union

from bencoding import bdecode, bencode
from bs4 import BeautifulSoup
from requests import get
from requests.compat import urlsplit
from requests.exceptions import ConnectionError as requests_ConnectionError

from backend.blocklist import add_to_blocklist, blocklist_contains
from backend.custom_exceptions import DownloadNotFound, LinkBroken
from backend.db import get_db
from backend.files import extract_filename_data
from backend.naming import (generate_issue_name, generate_issue_range_name,
                            generate_tpb_name)
from backend.post_processing import PostProcessing
from backend.search import _check_matching_titles
from backend.settings import Settings, blocklist_reasons, private_settings

from .lib.mega import Mega, RequestError

zs_regex = compile(r'document\.getElementById\(\'dlbutton\'\)\.href = "(.*?)" \+ \((\d+) % (\d+) \+ (\d+) % (\d+)\) \+ "(.*?)";')
file_extension_regex = compile(r'(?<=\.)[\w\d]{2,4}(?=$|;|\s)|(?<=\/)[\w\d]{2,4}(?=$|;|\s)', IGNORECASE)
issue_range_regex = compile(r'#?(\d+)\s?-\s?(\d+)', IGNORECASE)
mega_regex = compile(r'https?://mega\.(nz|io)/(#\!|file/)')
mediafire_regex = compile(r'https?://www.mediafire.com/file/')
download_chunk_size = 4194304 # 4MB Chunks
# Below is in order of preference
supported_source_strings = (('mega', 'mega link'),
							('mediafire', 'mediafire link'),
							('zippyshare', 'zippyshare link'),
							('direct', 'download now','main server','mirror download'))
source_preference_order = list(s[0] for s in supported_source_strings)

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
	def __init__(self, link: str, filename_body: str):
		"""Setup the direct download

		Args:
			link (str): The link (that leads to a file) that should be used
			filename_body (str): The body of the filename to write to

		Raises:
			LinkBroken: The link doesn't work
		"""
		logging.debug(f'Creating download: {link}, {filename_body}')
		super().__init__()
		self.progress: float = 0.0
		self.speed: float = 0.0
		self.link = link

		self.size: int = 0
		self.__r = get(self.link, stream=True)
		if not self.__r.ok:
			raise LinkBroken(1, blocklist_reasons[1])
		self.__filename_body = filename_body.rstrip('.')

		self.file = self.__build_filename(self.__r)
		self.title = splitext(basename(self.file))[0]

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

		self.size = int(self.__r.headers.get('content-length',-1))
		with open(self.file, 'wb') as f:
			start_time = perf_counter()
			for chunk in self.__r.iter_content(chunk_size=download_chunk_size):
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

	def __init__(self, link: str, filename_body: str):
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
		
		self.__r = get(self.link, stream=True)
		if not self.__r.ok:
			raise LinkBroken(1, blocklist_reasons[1])
		self.__filename_body = filename_body.rstrip('.')
		try:
			self._mega = Mega(link)
		except RequestError:
			raise LinkBroken(1, blocklist_reasons[1])

		self.file = self.__build_filename()
		self.title = splitext(basename(self.file))[0]
		
	def __extract_extension(self) -> str:
		"""Find the extension of the file behind the link

		Returns:
			str: The extension of the file, including the `.`
		"""
		extension = splitext(self._mega.mega_filename)[1]
		return extension

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
		dict: The pure link and a download instance for the correct service (e.g. DirectDownload or MegaDownload)
	"""
	logging.debug(f'Purifying link: {link}')
	# Go through every link and get it all down to direct download or magnet links
	if link.startswith('magnet:?'):
		# Link is already magnet link
		raise LinkBroken(2, blocklist_reasons[2])

	elif link.startswith('http'):
		if '.zippyshare.com/v/' in link:
			# Link is zippyshare
			r = get(link)
			m = zs_regex.search(r.text)
			if m:
				parsed_url = urlsplit(link)
				zs_id = int(m.group(2)) % int(m.group(3)) + int(m.group(4)) % int(m.group(5))
				zs_link = parsed_url.scheme + '://' + parsed_url.netloc + m.group(1) + str(zs_id) + m.group(6)
				return {'link': zs_link, 'target': DirectDownload}

		else:
			r = get(link, allow_redirects=False, stream=True)

			if mega_regex.search(link):
				# Link is mega
				return {'link': link, 'target': MegaDownload}

			elif mega_regex.search(r.headers.get('Location', '')):
				# Link is mega
				return {'link': r.headers['Location'], 'target': MegaDownload}

			elif mediafire_regex.search(link):
				# Link is mediafire
				soup = BeautifulSoup(r.text, 'html.parser')
				button = soup.find('a', {'id': 'downloadButton'})
				if button:
					return {'link': button['href'], 'target': DirectDownload}
				raise LinkBroken(1, blocklist_reasons[1])

			elif mediafire_regex.search(r.headers.get('Location', '')):
				# Link is mediafire
				r = get(link)
				soup = BeautifulSoup(r.text, 'html.parser')
				button = soup.find('a', {'id': 'downloadButton'})
				if button:
					return {'link': button['href'], 'target': DirectDownload}
				raise LinkBroken(1, blocklist_reasons[1])

			elif r.headers.get('Location','').startswith('magnet:?'):
				# Link is magnet link
				raise LinkBroken(2, blocklist_reasons[2])
				return {'link': r.headers['Location'], 'target': None}

			elif r.headers.get('Content-Type','') == 'application/x-bittorrent':
				# Link is torrent file
				raise LinkBroken(2, blocklist_reasons[2])
				hash = sha1(bencode(bdecode(r.content)[b"info"])).hexdigest()
				return {'link': "magnet:?xt=urn:btih:" + hash + "&tr=udp://tracker.cyberia.is:6969/announce&tr=udp://tracker.port443.xyz:6969/announce&tr=http://tracker3.itzmx.com:6961/announce&tr=udp://tracker.moeking.me:6969/announce&tr=http://vps02.net.orel.ru:80/announce&tr=http://tracker.openzim.org:80/announce&tr=udp://tracker.skynetcloud.tk:6969/announce&tr=https://1.tracker.eu.org:443/announce&tr=https://3.tracker.eu.org:443/announce&tr=http://re-tracker.uz:80/announce&tr=https://tracker.parrotsec.org:443/announce&tr=udp://explodie.org:6969/announce&tr=udp://tracker.filemail.com:6969/announce&tr=udp://tracker.nyaa.uk:6969/announce&tr=udp://retracker.netbynet.ru:2710/announce&tr=http://tracker.gbitt.info:80/announce&tr=http://tracker2.dler.org:80/announce",
							'target': None}

			elif link.startswith('https://getcomics.org/links.php/'):
				# Link is direct download from getcomics ('Main Server')
				r = get(link, allow_redirects=True, stream=True)
				return {'link': r.url, 'target': DirectDownload}

			else:
				raise LinkBroken(2, blocklist_reasons[2])
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
	for result in soup.find_all(link_filter_1):
		group_title: str = result.get_text('\x00').partition('\x00')[0]
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

	for result in soup.find_all(link_filter_2):
		group_title: str = result.get_text('\x00').partition('\x00')[0]
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
	link_paths: List[List[dict]] = []
	for desc, sources in download_groups.items():
		processed_desc = extract_filename_data(desc, assume_volume_number=False)
		if (_check_matching_titles(volume_title, processed_desc['series'])
		and (processed_desc['volume_number'] is None
			or
			processed_desc['volume_number'] == volume_number)
		and (processed_desc['special_version'] or processed_desc['issue_number'])
		):
			# Group matches/contains what is desired to be downloaded
			sources = {s: sources[s] for s in sorted(list(sources.keys()), key=lambda k: source_preference_order.index(k))}
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
	volume_id: int,
	issue_id: int=None
) -> List[dict]:
	"""Test the links of the paths and determine based on which links work which path to go for

	Args:
		link_paths (List[List[Dict[str, dict]]]): The link paths (output of download._process_extracted_get_comics_links())
		volume_id (int): The id of the volume
		issue_id (int, optional): The id of the issue. Defaults to None.

	Returns:
		List[dict]: A list of downloads.
	"""
	logging.debug('Testing paths')
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
				name = generate_issue_name(volume_id, issue_id)

			# Find working link
			for links in download['links'].values():
				for link in links:
					try:
						pure_link = _purify_link(link)
						dl_instance = pure_link['target'](link=pure_link['link'], filename_body=name)
					except LinkBroken as lb:
						# Link is broken
						add_to_blocklist(link, lb.reason_id)
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
	return downloads
		
def _extract_download_links(link: str, volume_id: int, issue_id: int=None) -> List[dict]:
	"""Filter, select and setup downloads from a getcomic page

	Args:
		link (str): Link to the getcomics page
		volume_id (int): The id of the volume for which the getcomics page is
		issue_id (int, optional): The id of the issue for which the getcomics page is. Defaults to None.

	Returns:
		List[dict]: List of downloads
	"""	
	logging.debug(f'Extracting download links from {link} for volume {volume_id} and issue {issue_id}')
	links = []

	try:
		r = get(link, stream=True)
		if not r.ok:
			raise requests_ConnectionError
	except requests_ConnectionError:
		# Link broken
		add_to_blocklist(link, 1)

	if link.startswith(private_settings['getcomics_url']) and not link.startswith(private_settings['getcomics_url'] + '/links.php/'):
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
		links = _test_paths(link_paths, volume_id, issue_id)

	else:
		# Link is a torrent file or magnet link
		pass

	return links

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
				PostProcessing(download).short()
				return
			# else
			download['instance'].state = IMPORTING_STATE
			PostProcessing(download).full()
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
			cursor = get_db('dict')
			cursor.execute("""
				SELECT
					id,
					link,
					volume_id, issue_id
				FROM download_queue;
			""")
			while True:
				download = cursor.fetchmany()
				if not download: break
				logging.debug(f'Download from database: {download}')
				self.add(download[0]['link'], download[0]['volume_id'], download[0]['issue_id'], download[0]['id'])
		return

	def add(self,
		link: str,
		volume_id: int, issue_id: int=None,
		_download_id_override: int=None
	) -> List[dict]:
		"""Add a download to the queue

		Args:
			link (str): A getcomics link to download from
			volume_id (int): The id of the volume for which the download is intended
			issue_id (int, optional): The id of the issue for which the download is intended. Defaults to None.
			_download_id_override (int, optional): Internal use only. Leave to None. Defaults to None.

		Returns:
			List[dict]: Queue entries that were added from the link.
		"""		
		logging.info(
			f'Adding download for volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: {link}'
		)
		
		# Extract download links and convert into Download instances
		# [{'name': 'Filename', 'link': 'link_on_getcomics_page', 'instance': Download_instance}]
		downloads = _extract_download_links(link, volume_id, issue_id)
		if not downloads:
			# No links extracted from page so add it to blocklist
			add_to_blocklist(link, 3)
			logging.warning('Unable to extract download links from source')
			return []

		result = []
		with self.context():
			cursor = get_db()
			for download in downloads:
				download['original_link'] = link
				download['volume_id'] = volume_id
				download['issue_id'] = issue_id
				download['thread'] = Thread(target=self.__run_download, args=(download,), name="Download Handler")
				
				if _download_id_override:
					download['id'] = _download_id_override
				else:
					download['id'] = cursor.execute("""
						INSERT INTO download_queue(link, volume_id, issue_id)
						VALUES (?,?,?);
						""",
						(link, volume_id, issue_id)
					).lastrowid

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
		# Delete download from database
		get_db().execute(
			"DELETE FROM download_queue WHERE id = ?",
			(download_id,)
		)

		# Delete download from queue
		for download in self.queue:
			if download['id'] == download_id:
				if download['instance'].state == DOWNLOADING_STATE:
					download['instance'].stop()
					download['thread'].join()
				self.queue.remove(download)
				break
		else:
			raise DownloadNotFound
		
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
			(offset,)
		).fetchall()
	))
	return result

def delete_download_history() -> None:
	"""Delete complete download history
	"""
	logging.info('Deleting download history')
	get_db().execute("DELETE FROM download_history;")
	return
