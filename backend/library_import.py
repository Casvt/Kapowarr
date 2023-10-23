#-*- coding: utf-8 -*-

import logging
from asyncio import create_task, gather, run
from os.path import basename, commonpath, dirname, splitext
from typing import Dict, List, Tuple, Union

from aiohttp import ClientSession

from backend.comicvine import ComicVine
from backend.custom_exceptions import VolumeAlreadyAdded
from backend.db import get_db
from backend.files import (_list_files, extract_filename_data, scan_files,
                           supported_extensions)
from backend.root_folders import RootFolders
from backend.search import _check_matching_titles
from backend.volumes import Library, Volume


def batched(l: list, n: int):
	"""Iterate over list (or tuple, set, etc.) in batches

	Args:
		l (list): The list to iterate over
		n (int): The batch size

	Yields:
		A batch of size n from l
	"""
	for ndx in range(0, len(l), n):
		yield l[ndx : ndx+n]

async def __search_matches(datas: List[dict]) -> List[dict]:
	comicvine = ComicVine()
	results: List[dict] = []
	async with ClientSession() as session:
		data_titles = {d['series'].lower() for d in datas}
		tasks = [
			create_task(comicvine.search_volumes_async(session, series)) for series in data_titles
		]
		responses = await gather(*tasks)
		title_to_response = dict(zip(data_titles, responses))

		for data in datas:
			matching_result = {}
			for result in title_to_response[data['series'].lower()]:
				if (_check_matching_titles(data['series'], result['title'])
				and ((
						data['year'] is not None
						and result['year'] is not None
						and 0 <= abs(data['year'] - result['year']) <= 1 # One year wiggle room
					)
					or result['year'] is None
				)):
					matching_result = result
					break

			results.append({
				'id': matching_result.get('comicvine_id'),
				'title': f"{matching_result['title']} ({matching_result['year']})" if matching_result else None,
				'link': matching_result.get('comicvine_info')
			})
			
		return results

def propose_library_import() -> List[dict]:
	"""Get list of unimported files and their suggestion for a matching volume on CV.

	Returns:
		List[dict]: The list of files and their matches.
	"""
	logging.info('Loading library import')

	# Get all files in all root folders
	root_folders = RootFolders().get_all()
	all_files = []
	for f in root_folders:
		all_files += _list_files(f['folder'], supported_extensions)
	
	# Remove all files that are already imported, 
	# also extract filename data
	cursor = get_db()
	imported_files = set(
		f[0] for f in cursor.execute(
			"SELECT filepath FROM files"
		)
	)

	# List with tuples. First entry is efd,
	# second is all matching files for that efd.
	unimported_files: List[Tuple[dict, List[str]]] = []
	for f in all_files:
		if not f in imported_files:
			efd = extract_filename_data(f)
			del efd['issue_number']

			for entry in unimported_files:
				if entry[0] == efd:
					entry[1].append(f)
					break
			else:
				unimported_files.append((
					efd,
					[f]
				))
	logging.debug(f'File groupings: {unimported_files}')

	# Find a match for the files on CV
	result: List[dict] = []
	for uf_batch in batched(unimported_files, 10):
		search_results = run(__search_matches([e[0] for e in uf_batch]))
		for group_number, (search_result, group_data) in enumerate(zip(search_results, uf_batch)):
			result += [
				{
					'filepath': f,
					'file_title': splitext(basename(f))[0],
					'cv': search_result,
					'group_number': group_number + 1
				}
				for f in group_data[1]
			]

	result.sort(key=lambda e: (e['group_number'], e['file_title']))

	return result

def import_library(matches: List[Dict[str, Union[str, int]]]) -> None:
	"""Add volume to library and import linked files

	Args:
		matches (List[Dict[str, Union[str, int]]]): List of dicts.
		The key `id` should supply the CV id of the volume and `filepath` the linked file.
	"""
	logging.info('Starting library import')
	id_to_filepath = {}
	for match in matches:
		id_to_filepath.setdefault(match['id'], []).append(match['filepath'])
	logging.debug(f'id_to_filepath: {id_to_filepath}')

	root_folders = RootFolders().get_all()

	library = Library()
	for cv_id, files in id_to_filepath.items():
		# Find lowest common folder
		volume_folder: str
		if len(files) == 1:
			volume_folder = dirname(files[0])
		else:
			volume_folder = commonpath(files)

		# Find root folder that lcf is in
		for root_folder in root_folders:
			if volume_folder.startswith(root_folder['folder']):
				root_folder_id = root_folder['id']
				break
		else:
			continue
		logging.debug(f'{cv_id} -> {volume_folder}')

		# Add volume if it isn't already
		try:
			volume_id = library.add(
				comicvine_id=str(cv_id),
				root_folder_id=root_folder_id,
				monitor=True,
				volume_folder=volume_folder
			)
			scan_files(Volume(volume_id).get_info())
		except VolumeAlreadyAdded:
			continue
	return
