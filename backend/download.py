#-*- coding: utf-8 -*-

"""This file contains functions regarding directly downloading content from getcomics.info
"""

import logging
from abc import ABC, abstractmethod
from hashlib import sha1
from os.path import basename, join, splitext
from re import IGNORECASE, compile
from threading import Thread
from time import perf_counter, sleep
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
from backend.settings import Settings, blocklist_reasons

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
		# Set from outside. Instance is 'tagged' with a few variables
		self.id: int
		self.original_link: str
		self.volume_id: int
		self.issue_id: int
		
		self.state: str = QUEUED_STATE

class DirectDownload(BaseDownload):
	def __init__(self, link: str, filename_body: str):
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
		folder = Settings().get_settings()['download_folder']
		extension = self.__extract_extension(
			r.headers.get('Content-Type', ''),
			r.headers.get('Content-Disposition', ''),
			r.url
		)
		return join(folder, self.__filename_body + extension)

	def run(self) -> None:
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
		extension = splitext(self._mega.mega_filename)[1]
		return extension

	def __build_filename(self) -> str:
		folder = Settings().get_settings()['download_folder']
		extension = self.__extract_extension()
		return join(folder, self.__filename_body + extension)

	def run(self) -> None:
		self.state = DOWNLOADING_STATE
		self._mega.download_url(self.file)

	def stop(self) -> None:
		self.state = CANCELED_STATE
		self._mega.downloading = False

#=====================
# Download link analysation
#=====================
def _check_download_link(link_text: str, link: str) -> Union[str, None]:
	if not link:
		return

	# Check if link is in blocklist
	if blocklist_contains(link):
		return

	# Check if link is from supported source
	for source in supported_source_strings:
		if link_text in source:
			return source[0]

	return

def _purify_link(link: str) -> dict:
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

			elif link.startswith('https://getcomics.info/links.php/'):
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
	if p[0]['info']['special_version']:
		return 0
	return 1 / len(p)
	
def _process_extracted_get_comics_links(
	download_groups: Dict[str, Dict[str, List[str]]],
	volume_title: str,
	volume_number: int
) -> List[List[Dict[str, Dict[str, List[str]]]]]:

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
	link_paths: List[List[Dict[str, Dict[str, List[str]]]]],
	volume_id: int,
	issue_id: int
) -> List[dict]:

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
	
	logging.debug(f'Chosen links: {[{"name": download["name"], "link": download["link"]} for download in downloads]}')
	return downloads
		
def _extract_download_links(link: str, volume_id: int, issue_id: int=None) -> List[dict]:
	links = []

	try:
		r = get(link, stream=True)
		if not r.ok:
			raise requests_ConnectionError
	except requests_ConnectionError:
		# Link broken
		add_to_blocklist(link, 1)

	if link.startswith('https://getcomics.info/') and not link.startswith('https://getcomics.info/links.php/'):
		# Link is to a getcomics page

		# Get info of volume
		volume_info = get_db('dict').execute(
			"SELECT title, volume_number FROM volumes WHERE id = ?",
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
		# [{'name': 'Filename', 'link': 'link_on_getcomics_page', 'instance': 'Download_instance'}]
		links = _test_paths(link_paths, volume_id, issue_id)

	else:
		# Link is a torrent file or magnet link
		links = []

	return links

#=====================
# Download handling
#=====================
class DownloadHandler:
	queue = []
	stop = False
	
	def __init__(self, context):
		self.context = context.app_context
		self.thread = Thread(target=self.handle, name='Download Handler')

	def __load_downloads(self) -> None:
		with self.context():
			previous_downloads = get_db('dict').execute("""
				SELECT
					id,
					original_link, root_download_link,
					filename_body,
					volume_id, issue_id
				FROM download_queue;
			""").fetchall()
			
			for previous_download in previous_downloads:
				try:
					pure_link = _purify_link(previous_download['root_download_link'])
					dl_instance = pure_link['target'](link=pure_link['link'], filename_body=previous_download['filename_body'])
				except LinkBroken as lb:
					# Link broken
					add_to_blocklist(previous_download['root_download_link'], lb.reason_id)
		
				download = self.__build_new_entry(
					dl_instance,
					previous_download['original_link'], previous_download['root_download_link'],
					previous_download['volume_id'], previous_download['issue_id'],
					previous_download['id']
				)
				self.queue.append(download)
				logging.debug(f'Loaded download from database: {previous_download["original_link"]}->{previous_download["root_download_link"]}')
		return

	def __run_download(self, entry: Download) -> None:
		logging.info(f'Starting download: {entry.id}')

		with self.context():
			entry.run()

			if entry.state == CANCELED_STATE:
				PostProcessing(entry).short()
			else:
				entry.state = IMPORTING_STATE
				PostProcessing(entry).full()

			return

	def handle(self) -> None:
		"""This function is intended to be run in a thread
		"""
		self.__load_downloads()

		while self.stop == False:
			if len(self.queue) > 0:
				entry = self.queue[0]
				self.__run_download(entry)
				self.queue.pop(0)
			else:
				sleep(2)
		return

	def stop_handle(self) -> None:
		logging.debug('Stopping download thread')
		if len(self.queue) > 0:
			self.queue[0].stop()
		self.stop = True
		self.thread.join()
		return

	def __format_entry(self, d: Download) -> dict:
		return {
			'id': d.id,
			'status': d.state,
			'link': d.link,
			'original_link': d.original_link,
			'file': d.file,
			'size': d.size,
			'title': d.title,
			'progress': d.progress,
			'speed': d.speed,
			'volume_id': d.volume_id,
			'issue_id': d.issue_id
		}

	def __build_new_entry(
		self,
		download: Download,
		original_link: str,
		root_download_link: str,
		volume_id: int,
		issue_id: int,
		id_override: int=None
	) -> Download:
		cursor = get_db()
		
		# Generate id
		if id_override is None:
			id = cursor.execute(
				"""
				INSERT INTO download_queue(
					original_link,
					root_download_link,
					filename_body,
					volume_id,
					issue_id
				) VALUES (?,?,?,?,?)
				""",
				(original_link, root_download_link, download.title, volume_id, issue_id)
			).lastrowid
		else:
			id = id_override

		# Add tags to download
		download.id = id
		download.original_link = original_link
		download.volume_id = volume_id
		download.issue_id = issue_id

		return download

	def add(self, link: str, volume_id: int, issue_id: int=None) -> List[dict]:
		logging.info(f'Adding download for volume {volume_id}{f" issue {issue_id}" if issue_id else ""}: {link}')

		# Extract download links and convert into Download instances
		downloads = _extract_download_links(link, volume_id, issue_id)
		if not downloads:
			# No links extracted from page so add it to blocklist
			add_to_blocklist(link, 3)

		result = []
		for download in downloads:
			download = self.__build_new_entry(download['instance'], link, download['link'], volume_id, issue_id)

			# Add to queue
			result.append(self.__format_entry(download))
			self.queue.append(download)

		return result

	def get_all(self) -> List[dict]:
		result = list(map(self.__format_entry, self.queue))
		return result

	def get_one(self, download_id: int) -> dict:
		for t in self.queue:
			if t.id == download_id:
				return self.__format_entry(t)
		raise DownloadNotFound

	def remove(self, download_id: int) -> None:
		result = get_db().execute(
			"DELETE FROM download_queue WHERE id = ?",
			(download_id,)
		).rowcount > 0
		if not result:
			raise DownloadNotFound

		for i, t in enumerate(self.queue):
			if t.id == download_id:
				if t.state == DOWNLOADING_STATE:
					t.stop()
				else:
					self.queue.pop(i)
				break

		logging.info(f'Removed download with id {download_id}')
		return

#=====================
# Download History Managing
#=====================
def get_download_history(offset: int=0) -> List[dict]:
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
	get_db().execute("DELETE FROM download_history;")
	logging.info('Deleted download history')
	return
