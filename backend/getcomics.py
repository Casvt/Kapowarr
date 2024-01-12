#-*- coding: utf-8 -*-

"""
Getting downloads from a GC page
"""

import logging
from hashlib import sha1
from re import IGNORECASE, compile
from typing import Dict, List, Tuple, Union

from bencoding import bdecode, bencode
from bs4 import BeautifulSoup, Tag
from requests import get
from requests.exceptions import ConnectionError as requests_ConnectionError

from backend.blocklist import add_to_blocklist, blocklist_contains
from backend.custom_exceptions import DownloadLimitReached, LinkBroken
from backend.db import get_db
from backend.download_direct_clients import (DirectDownload, Download,
                                             MegaDownload)
from backend.download_torrent_clients import TorrentDownload
from backend.enums import BlocklistReason, SpecialVersion
from backend.file_extraction import extract_filename_data
from backend.matching import GC_group_filter
from backend.naming import (generate_empty_name, generate_issue_name,
                            generate_issue_range_name, generate_tpb_name)
from backend.settings import Settings, supported_source_strings
from backend.volumes import Volume

check_year = compile(r'\b\d{4}\b')
mega_regex = compile(r'https?://mega\.(nz|io)/(#(F\!|\!)|folder/|file/)', IGNORECASE)
mediafire_regex = compile(r'https?://www\.mediafire\.com/', IGNORECASE)
extract_mediafire_regex = compile(
	r'window.location.href\s?=\s?\'https://download\d+\.mediafire.com/.*?(?=\')',
	IGNORECASE
)

def _check_download_link(
	link_text: str,
	link: str,
	torrent_client_available: bool
) -> Union[str, None]:
	"""Check if download link is supported and allowed.

	Args:
		link_text (str): The title of the link.
		link (str): The link itself.
		torrent_client_available (bool): Whether or not a torrent client is available.

	Returns:
		Union[str, None]: Either the name of the service (e.g. `mega`)
		or `None` if it's not allowed.
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
		if any(s in link_text for s in source):
			logging.debug(f'Checking download link: {link_text} maps to {source[0]}')
			
			if 'torrent' in source[0] and not torrent_client_available:
				return
			
			return source[0]

	return

def _purify_link(link: str) -> dict:
	"""Extract the link that directly leads to the download from the link
	on the getcomics page

	Args:
		link (str): The link on the getcomics page

	Raises:
		LinkBroken: Link is invalid, not supported or broken

	Returns:
		dict: The pure link,
		a download instance for the correct service (child of `download_general.Download`)
		and the source title.
	"""
	logging.debug(f'Purifying link: {link}')
	# Go through every link and get it all down to direct download or magnet links
	if link.startswith('magnet:?'):
		# Link is already magnet link
		return {
			'link': link,
			'target': TorrentDownload,
			'source': 'getcomics (torrent)'
		}

	elif link.startswith('http'):
		r = get(link, headers={'User-Agent': 'Kapowarr'}, stream=True)
		url = r.url
		
		if mega_regex.search(url):
			# Link is mega
			if '#F!' in url:
				# Link is not supported (folder)
				raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)
			
			if '/folder/' in url:
				# Link is not supported (folder)
				raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)
			
			return {'link': url, 'target': MegaDownload, 'source': 'mega'}
		
		elif mediafire_regex.search(url):
			# Link is mediafire
			if 'error.php' in url:
				# Link is broken
				raise LinkBroken(BlocklistReason.LINK_BROKEN)
			
			elif '/folder/' in url:
				# Link is not supported
				raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)

			result = extract_mediafire_regex.search(r.text)
			if result:
				return {
					'link': result.group(0).split("'")[-1],
					'target': DirectDownload,
					'source': 'mediafire'
				}
			
			soup = BeautifulSoup(r.text, 'html.parser')
			button = soup.find('a', {'id': 'downloadButton'})
			if button:
				return {
					'link': button['href'],
					'target': DirectDownload,
					'source': 'mediafire'
				}

			# Link is not broken and not a folder
			# but we still can't find the download button...
			raise LinkBroken(BlocklistReason.LINK_BROKEN)

		elif r.headers.get('Content-Type','') == 'application/x-bittorrent':
			# Link is torrent file
			hash = sha1(bencode(bdecode(r.content)[b"info"])).hexdigest()
			return {
				'link': "magnet:?xt=urn:btih:" + hash + "&tr=udp://tracker.cyberia.is:6969/announce&tr=udp://tracker.port443.xyz:6969/announce&tr=http://tracker3.itzmx.com:6961/announce&tr=udp://tracker.moeking.me:6969/announce&tr=http://vps02.net.orel.ru:80/announce&tr=http://tracker.openzim.org:80/announce&tr=udp://tracker.skynetcloud.tk:6969/announce&tr=https://1.tracker.eu.org:443/announce&tr=https://3.tracker.eu.org:443/announce&tr=http://re-tracker.uz:80/announce&tr=https://tracker.parrotsec.org:443/announce&tr=udp://explodie.org:6969/announce&tr=udp://tracker.filemail.com:6969/announce&tr=udp://tracker.nyaa.uk:6969/announce&tr=udp://retracker.netbynet.ru:2710/announce&tr=http://tracker.gbitt.info:80/announce&tr=http://tracker2.dler.org:80/announce",
				'target': TorrentDownload,
				'source': 'getcomics (torrent)'
			}

		# Link is direct download from getcomics
		# ('Main Server', 'Mirror Server', 'Link 1', 'Link 2', etc.)
		return {'link': url, 'target': DirectDownload, 'source': 'getcomics'}

	else:
		raise LinkBroken(BlocklistReason.SOURCE_NOT_SUPPORTED)

link_filter_1 = lambda e: (
	e.name == 'p'
	and 'Language' in e.text
	and e.find('p') is None
)
def _extract_button_links(
	body: Tag,
	torrent_client_available: bool
) -> dict:
	"""Extract download groups that are a list of big buttons.

	Args:
		body (Tag): The body to extract from.
		torrent_client_available (bool): Whether or not a client is available.

	Returns:
		dict: The download groups.
		Follows format described in `_extract_get_comics_links()`.
	"""
	download_groups = {}
	for result in body.find_all(link_filter_1):
		extracted_title: str = result.get_text('\x00')
		title: str = extracted_title.partition('\x00')[0]

		if 'variant cover' in title.lower():
			continue

		if (
			"Year :\x00\xa0" in extracted_title
			and not check_year.search(title)
		):
			# Append year to title
			year: str = (
				extracted_title
					.split("Year :\x00\xa0")[1]
					.split(" |")[0]
			)
			title += ' --' + year + '--'

		for e in result.next_sibling.next_elements:
			if e.name == 'div':
				print()
				print(e.attrs.get('class', []))
				print()
			if e.name == 'hr':
				break

			elif (
				e.name == 'div'
				and 'aio-button-center' in (e.attrs.get('class', []))
			):
				group_link: Tag = e.find('a')
				link_title = group_link.text.strip().lower()
				match = _check_download_link(
					link_title,
					group_link['href'],
					torrent_client_available
				)
				if match:
					(download_groups
						.setdefault(title, {})
						.setdefault(match, [])
						.append(group_link['href'])
					)

	return download_groups

link_filter_2 = lambda e: (
	e.name == 'li'
	and e.parent.name == 'ul'
	and e.find('a')
)
def _extract_list_links(
	body: Tag,
	torrent_client_available: bool
) -> dict:
	"""Extract download groups that are in a unsorted list.

	Args:
		body (Tag): The body to extract from.
		torrent_client_available (bool): Whether or not a client is available.

	Returns:
		dict: The download groups.
		Follows format described in `_extract_get_comics_links()`.
	"""
	download_groups = {}
	for result in body.find_all(link_filter_2):
		title: str = result.get_text('\x00').partition('\x00')[0]

		if 'variant cover' in title.lower():
			continue

		for group_link in result.find_all('a'):
			group_link: Tag
			link_title = group_link.text.strip().lower()
			match = _check_download_link(
				link_title,
				group_link['href'],
				torrent_client_available
			)
			if match:
				(download_groups
					.setdefault(title, {})
					.setdefault(match, [])
					.append(group_link['href'])
				)
	
	return download_groups

def _extract_get_comics_links(
	soup: BeautifulSoup
) -> Dict[str, Dict[str, List[str]]]:
	"""Go through the getcomics page and extract all download links.
	The links are grouped. All links in a group lead to the same download,
	only via different services (mega, direct download, mirror download, etc.).

	Args:
		soup (BeautifulSoup): The soup of the getcomics page.

	Returns:
		Dict[str, Dict[str, List[str]]]: The outer dict maps the group name to the group.
		The group is a dict that maps each service in the group to a list of links
		for that service.
		Example:
			{
				'Amazing Spider-Man V1 Issue 1-10': {
					'mega': ['https://mega.io/abc'],
					'direct': [
						'https://main.server.com/abc',
						'https://mirror.server.com/abc'
					]
				},
				'Amazing Spider-Man V1 Issue 11-20': {...}
			}
	"""
	logging.debug('Extracting download groups')

	torrent_client_available = get_db().execute(
		"SELECT 1 FROM torrent_clients"
	).fetchone() is not None

	body = soup.find('section', {'class': 'post-contents'})
	download_groups = {
		**_extract_button_links(body, torrent_client_available),
		**_extract_list_links(body, torrent_client_available)
	}

	logging.debug(f'Download groups: {download_groups}')
	return download_groups

def _sort_link_paths(p: List[dict]) -> Tuple[float, int]:
	"""Sort the link paths. TPB's are sorted highest, then from largest range to least.

	Args:
		p (List[dict]): A link path

	Returns:
		Tuple[float, int]: The rating (lower is better)
	"""	
	if p[0]['info']['special_version']:
		return (0.0, 0)

	issues_covered = 0
	for entry in p:
		if isinstance(entry['info']['issue_number'], float):
			issues_covered += 1
		elif isinstance(entry['info']['issue_number'], tuple):
			issues_covered += (
				entry['info']['issue_number'][1]
				-
				entry['info']['issue_number'][0]
			)

	return (1 / issues_covered, len(p))

def _check_overlapping_issues(
		issues_1: Union[float, Tuple[float, float]],
		issues_2: Union[float, Tuple[float, float]]
) -> bool:
	"""Check if two issues overlap. Both can be single issues or ranges.

	Args:
		issues_1 (Union[float, Tuple[float, float]]): First issue or range.
		issues_2 (Union[float, Tuple[float, float]]): Second issue or range.

	Returns:
		bool: Whether or not they overlap.
	"""
	if isinstance(issues_1, float):
		if isinstance(issues_2, float):
			return issues_1 == issues_2
		else:
			return issues_2[0] <= issues_1 <= issues_2[1]
	else:
		if isinstance(issues_2, float):
			return issues_1[0] <= issues_2 <= issues_1[1]
		else:
			return (issues_1[0] <= issues_2[0] <= issues_1[1]
				or issues_1[0] <= issues_2[1] <= issues_1[1])

def _create_link_paths(
	download_groups: Dict[str, Dict[str, List[str]]],
	volume_id: int
) -> List[List[Dict[str, dict]]]:
	"""Based on the download groups, find different "paths" to download
	the most amount of content. On the same page, there might be a download
	for `TPB + Extra's`, `TPB`, `Issue A-B` and for `Issue C-D`. This function
	creates "paths" that contain links that together download as much content
	without overlapping. So a path would be created for `TPB + Extra's`. A
	second path would be created for `TPB` and a third path for
	`Issue A-B` + `Issue C-D`. Paths 2 and on are basically backup options for
	if path 1 doesn't work, to still get the most content out of the page.

	Args:
		download_groups (Dict[str, Dict[str, List[str]]]): The download groups.
		Output of `download._extract_get_comics_links()`.
		volume_id (int): The id of the volume.

	Returns:
		List[List[Dict[str, dict]]]: The list contains all paths. Each path is
		a list of download groups. The `info` key has as it's value the output 
		of `file_extraction.extract_filename_data()` for the title of the group.
		The `links` key contains the download links grouped together with
		their service.
	"""	
	logging.debug('Creating link paths')

	# Get info of volume
	volume = Volume(volume_id)
	volume_data = volume.get_keys(
		('title', 'year', 'special_version')
	)
	last_issue_date = volume['last_issue_date']
	service_preference: List[str] = Settings()['service_preference']

	link_paths: List[List[dict]] = []
	for desc, sources in download_groups.items():
		processed_desc = extract_filename_data(desc, assume_volume_number=False)
		if GC_group_filter(
			processed_desc,
			volume_id,
			volume_data.title,
			volume_data.year,
			last_issue_date,
			volume_data.special_version
		):
			# Group matches/contains what is desired to be downloaded
			sources = {
				s: sources[s]
				for s in sorted(
					sources,
					key=lambda k: service_preference.index(k)
				)
			}
			if (volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE
			and (
				processed_desc['special_version'] == SpecialVersion.TPB
				or isinstance(processed_desc['volume_number'], tuple)
			)):
				processed_desc['special_version'] = SpecialVersion.VOLUME_AS_ISSUE.value

			if (
				processed_desc['special_version'] is not None
				and processed_desc['special_version'] != SpecialVersion.VOLUME_AS_ISSUE
			):
				if volume_data.special_version in (
					SpecialVersion.HARD_COVER,
					SpecialVersion.ONE_SHOT
				):
					processed_desc['special_version'] = volume_data.special_version.value

				link_paths.append([{'info': processed_desc, 'links': sources}])

			else:
				# Find path with ranges and single issues that doesn't have 
				# a link that already covers this one
				for path in link_paths:
					for entry in path:
						if entry['info']['special_version'] == SpecialVersion.VOLUME_AS_ISSUE:
							if entry['info']['volume_number'] == processed_desc['volume_number']:
								break

						elif entry['info']['special_version'] is not None:
							break

						elif _check_overlapping_issues(
							entry['info']['issue_number'],
							processed_desc['issue_number']
						):
							break

					else:
						# No conflicts found so add to path
						path.append({'info': processed_desc, 'links': sources})
						break
				else:
					# Conflict in all paths found so start a new one
					link_paths.append([{'info': processed_desc, 'links': sources}])
	
	link_paths.sort(key=_sort_link_paths)

	logging.debug(f'Link paths: {link_paths}')
	return link_paths

def _generate_name(
	volume_id: int,
	download_info: dict,
	name_volume_as_issue: bool
) -> str:
	"""Generate filename based on info.

	Args:
		volume_id (int): The ID of the volume for which the file is.
		download_info (dict): Output of `file_extraction.extract_filename_data()`
		for download group title.
		name_volume_as_issue (bool): Whether or not to name the volume as an
		issue.

	Returns:
		str: The generated name.
	"""
	if download_info['special_version'] == SpecialVersion.TPB:
		return generate_tpb_name(volume_id)

	if download_info['special_version'] == SpecialVersion.VOLUME_AS_ISSUE:
		if name_volume_as_issue:
			if isinstance(download_info['volume_number'], tuple):
				return generate_issue_range_name(
					volume_id,
					*download_info['volume_number']
				)
			else:
				return generate_issue_name(
					volume_id,
					download_info['volume_number']
				)
		else:
			return generate_empty_name(
				volume_id,
				download_info['volume_number']
			)

	if download_info['special_version'] is not None:
		return generate_empty_name(volume_id)

	if isinstance(download_info['issue_number'], tuple):
		return generate_issue_range_name(
			volume_id,
			*download_info['issue_number']
		)

	return generate_issue_name(
		volume_id,
		download_info['issue_number']
	)

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
	cursor = get_db()
	limit_reached = False
	downloads: List[Download] = []
	settings = Settings()
	rename_downloaded_files = settings['rename_downloaded_files']
	name_volume_as_issue = settings['volume_as_empty']
	for path in link_paths:
		for download in path:
			if rename_downloaded_files:
				name = _generate_name(
					volume_id,
					download['info'],
					name_volume_as_issue
				)
				
			else:
				name = ''

			# Find working link
			for links in download['links'].values():
				for link in links:
					try:
						## Maybe make purify link async so that all links can be purified 'at the same time'?
						pure_link = _purify_link(link)
						dl_instance = pure_link['target'](
							link=pure_link['link'],
							filename_body=name,
							source=pure_link['source'],
							custom_name=rename_downloaded_files
						)

					except LinkBroken as lb:
						# Link is broken
						add_to_blocklist(link, lb.reason)
						cursor.connection.commit()

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
			if downloads:
				break
			else:
				# Try next path
				continue
		downloads = []
	
	logging.debug(f'Chosen links: {downloads}')
	return downloads, limit_reached
		
def extract_GC_download_links(
	link: str,
	volume_id: int,
	issue_id: int = None
) -> Tuple[List[dict], bool]:
	"""Filter, select and setup downloads from a getcomic page

	Args:
		link (str): Link to the getcomics page
		volume_id (int): The id of the volume for which the getcomics page is
		issue_id (int, optional): The id of the issue for which the getcomics page is. Defaults to None.

	Returns:
		Tuple[List[dict], bool]: List of downloads and whether or not the download limit for a service on the page is reached.

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
		return [], True

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
