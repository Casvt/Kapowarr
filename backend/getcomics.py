#-*- coding: utf-8 -*-

import logging
from hashlib import sha1
from re import IGNORECASE, compile
from typing import Dict, List, Tuple, Union

from bencoding import bdecode, bencode
from bs4 import BeautifulSoup
from requests import get
from requests.exceptions import ConnectionError as requests_ConnectionError

from backend.blocklist import add_to_blocklist, blocklist_contains
from backend.custom_exceptions import DownloadLimitReached, LinkBroken
from backend.db import get_db
from backend.download_clients import (DirectDownload, Download, MegaDownload,
                                      credentials)
from backend.files import extract_filename_data
from backend.naming import (generate_empty_name, generate_issue_name,
                            generate_issue_range_name, generate_tpb_name)
from backend.search import _check_matching_titles
from backend.settings import (Settings, blocklist_reasons, private_settings,
                              supported_source_strings)

mega_regex = compile(r'https?://mega\.(nz|io)/(#(F\!|\!)|folder/|file/)', IGNORECASE)
mediafire_regex = compile(r'https?://www\.mediafire\.com/', IGNORECASE)
extract_mediafire_regex = compile(r'window.location.href\s?=\s?\'https://download\d+\.mediafire.com/.*?(?=\')', IGNORECASE)

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
	
	# Check if link is from a service that should be avoided
	if link.startswith('https://sh.st/'):
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

			result = extract_mediafire_regex.search(r.text)
			if result:
				return {'link': result.group(0).split("'")[-1], 'target': DirectDownload, 'source': 'mediafire'}
			
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
check_year = compile(r'\b\d{4}\b')
def _extract_get_comics_links(
	soup: BeautifulSoup
) -> Dict[str, Dict[str, List[str]]]:
	"""Go through the getcomics page and extract all download links.
	The links are grouped. All links in a group lead to the same download,
	only via different services (mega, direct download, mirror download, etc.)

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
	body = soup.find('section', {'class': 'post-contents'})
	for result in body.find_all(link_filter_1):
		extracted_title = result.get_text('\x00')
		group_title: str = extracted_title.partition('\x00')[0]
		if "Year :\x00\xa0" in extracted_title and not check_year.search(group_title):
			# Append year to title
			group_title += ' --' + result.get_text("\x00").split("Year :\x00\xa0")[1].split(" |")[0] + '--'

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
	
def _create_link_paths(
	download_groups: Dict[str, Dict[str, List[str]]],
	volume_id: int
) -> List[List[Dict[str, dict]]]:
	"""Based on the download groups, find different "paths" to download the most amount of content.
	On the same page, there might be a download for `TPB + Extra's`, `TPB`, `Issue A-B` and for `Issue C-D`.
	This function creates "paths" that contain links that together download as much content without overlapping.
	So a path would be created for `TPB + Extra's`. A second path would be created for `TPB` and a third path for
	`Issue A-B` + `Issue C-D`. Paths 2 and on are basically backup options for if path 1 doesn't work, to still get
	the most content out of the page.

	Args:
		download_groups (Dict[str, Dict[str, List[str]]]): The download groups (output of download._extract_get_comics_links())
		volume_id (int): The id of the volume

	Returns:
		List[List[Dict[str, dict]]]: The list contains all paths. Each path is a list of download groups. The `info` key has
		as it's value the output of files.extract_filename_data() for the title of the group. The `links` key contains the
		download links grouped together with their service.
	"""	
	logging.debug('Creating link paths')

	# Get info of volume
	cursor = get_db()
	volume_title: str
	volume_number: int
	volume_year: int
	special_version: int
	last_issue_date: str
	volume_title, volume_number, volume_year, special_version, last_issue_date = cursor.execute("""
		SELECT
			v.title,
			volume_number,
			year,
			special_version,
			MAX(i.date) AS last_issue_date
		FROM volumes v
		INNER JOIN issues i
		ON v.id = i.volume_id
		WHERE v.id = ?
		LIMIT 1;
		""",
		(volume_id,)
	).fetchone()
	last_year: int = int(last_issue_date.split('-')[0]) if last_issue_date else volume_year
	annual = 'annual' in volume_title.lower()
	service_preference_order = dict((v, k) for k, v in enumerate(Settings().get_service_preference()))

	link_paths: List[List[dict]] = []
	for desc, sources in download_groups.items():
		processed_desc = extract_filename_data(desc, assume_volume_number=False)
		if (_check_matching_titles(volume_title, processed_desc['series'])
		and (processed_desc['volume_number'] is None
			or ((
					isinstance(processed_desc['volume_number'], int)
					and processed_desc['volume_number'] == volume_number
				)
				or (
					isinstance(processed_desc['volume_number'], tuple)
					and special_version == 'volume-as-issue'
				))
			or (
				isinstance(processed_desc['volume_number'], int)
				and volume_year - 1 <= processed_desc['volume_number'] <= volume_year
			)
			or (
				special_version == 'volume-as-issue'
				and
				cursor.execute(
					"SELECT 1 FROM issues WHERE volume_id = ? AND calculated_issue_number = ? LIMIT 1;",
					(volume_id, processed_desc['volume_number'])
				).fetchone()
			))
		and (processed_desc['year'] is None
			or
			volume_year - 1 <= processed_desc['year'] <= last_year)
		and (special_version == processed_desc['special_version']
			or (
				special_version in ('hard-cover', 'volume-as-issue')
				and processed_desc['special_version'] == 'tpb'
			)
			or
			processed_desc['issue_number'])
		and processed_desc['annual'] == annual
		):
			# Group matches/contains what is desired to be downloaded
			sources = {s: sources[s] for s in sorted(sources, key=lambda k: service_preference_order[k])}
			if (special_version == 'volume-as-issue'
			and (
				processed_desc['special_version'] == 'tpb'
				or isinstance(processed_desc['volume_number'], tuple)
			)):
				processed_desc['special_version'] = special_version

			if (processed_desc['special_version'] is not None
			and processed_desc['special_version'] != 'volume-as-issue'):
				if special_version == 'hard-cover':
					processed_desc['special_version'] = 'hard-cover'
				link_paths.append([{'info': processed_desc, 'links': sources}])

			else:
				# Find path with ranges and single issues that doesn't have a link that already covers this one
				for path in link_paths:
					for entry in path:
						if entry['info']['special_version'] == 'volume-as-issue':
							if entry['info']['volume_number'] == processed_desc['volume_number']:
								break

						elif entry['info']['special_version'] is not None:
							break

						elif isinstance(entry['info']['issue_number'], float):
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
) -> Tuple[List[Download], bool]:
	"""Test the links of the paths and determine, based on which links work, which path to go for.

	Args:
		link_paths (List[List[Dict[str, dict]]]): The link paths (output of `download._process_extracted_get_comics_links()`).
		volume_id (int): The id of the volume.

	Returns:
		Tuple[List[Download], bool]: A list of downloads and wether or not the download limit for a service on the page is reached.

		If the list is empty and the bool is False, the page doesn't have any working links and can be blacklisted.

		If the list is empty and the bool is True, the page has working links but the service of the links has reached it's download limit, so nothing on the page can be downloaded.
		However, the page shouldn't be blacklisted because the links _are_ working.
		
		If the list has content, the page has working links that can be used.
	"""
	logging.debug('Testing paths')
	limit_reached = False
	downloads: List[Download] = []
	s = Settings().get_settings()
	rename_downloaded_files = s['rename_downloaded_files']
	name_volume_as_issue = s['volume_as_empty']
	for path in link_paths:
		for download in path:
			if rename_downloaded_files:
				# Generate name
				if download['info']['special_version'] == 'tpb':
					name = generate_tpb_name(volume_id)

				elif download['info']['special_version'] == 'volume-as-issue':
					if name_volume_as_issue:
						if isinstance(download['info']['volume_number'], tuple):
							name = generate_issue_range_name(
								volume_id,
								*download['info']['volume_number']
							)
						else:
							name = generate_issue_name(
								volume_id,
								download['info']['volume_number']
							)
					else:
						name = generate_empty_name(volume_id, download['info']['volume_number'])

				elif (download['info']['special_version'] or 'volume-as-issue') != 'volume-as-issue':
					name = generate_empty_name(volume_id)

				elif isinstance(download['info']['issue_number'], tuple):
					# Link for issue range
					name = generate_issue_range_name(
						volume_id,
						*download['info']['issue_number']
					)
				
				else:
					# Link for single issue
					name = generate_issue_name(volume_id, download['info']['issue_number'])
			else:
				name = ''

			# Find working link
			for links in download['links'].values():
				for link in links:
					try:
						# Maybe make purify link async so that all links can be purified 'at the same time'?
						# https://www.youtube.com/watch?v=nFn4_nA_yk8&t=1053s
						# https://stackoverflow.com/questions/53336675/get-aiohttp-results-as-string
						pure_link = _purify_link(link)
						dl_instance = pure_link['target'](
							link=pure_link['link'],
							filename_body=name,
							source=pure_link['source'],
							custom_name=rename_downloaded_files
						)

					except LinkBroken as lb:
						# Link is broken
						add_to_blocklist(link, lb.reason_id)

					except DownloadLimitReached:
						# Link works but the download limit for the service is reached
						limit_reached = True

					else:
						downloads.append(dl_instance)
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

	if link.startswith(private_settings['getcomics_url']):
		# Link is to a getcomics page
		soup = BeautifulSoup(r.text, 'html.parser')

		# Extract the download groups and filter invalid links
		download_groups = _extract_get_comics_links(soup)

		# Filter incorrect download groups and combine them (or not) to create download paths
		link_paths = _create_link_paths(
			download_groups,
			volume_id
		)

		# Decide which path to take by testing the links
		return _test_paths(link_paths, volume_id)

	return [], False
