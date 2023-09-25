#-*- coding: utf-8 -*-

import logging
from os.path import basename, commonpath, dirname, splitext
from typing import Dict, List, Tuple, Union

from backend.comicvine import ComicVine
from backend.custom_exceptions import VolumeAlreadyAdded
from backend.db import get_db
from backend.files import (_list_files, extract_filename_data, scan_files,
                           supported_extensions)
from backend.root_folders import RootFolders
from backend.search import _check_matching_titles
from backend.volumes import Library, Volume


def propose_library_import() -> List[dict]:
	"""Get list of unimported files and their suggestion for a matching volume on CV.

	Returns:
		List[dict]: The list of files and their matches.
	"""
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
	unimported_files = []
	for f in all_files:
		if not f in imported_files:
			efd = extract_filename_data(f)
			del efd['issue_number']
			result = {
				'filepath': f,
				'file_title': splitext(basename(f))[0],
				'data': efd
			}
			unimported_files.append(result)

	# Find a match for the file on CV
	comicvine = ComicVine()
	cv_to_data: List[Tuple[dict, dict]] = []
	for f in unimported_files:
		for cv, data in cv_to_data:
			if f['data'] == data:
				f['cv'] = cv
				del f['data']
				break
		else:
			search_results = comicvine.search_volumes(f['data']['series'])
			matching_result = next(
				(r for r in search_results
				if _check_matching_titles(f['data']['series'], r['title'])
					and f['data']['volume_number'] == r['volume_number']
					and ((
							f['data']['year'] is not None
							and r['year'] is not None
							and 0 <= abs(f['data']['year'] - r['year']) <= 1 # One year wiggle room
						)
						or r['year'] is None
					)),

				{}
			)
			cv_data = {
				'id': matching_result.get('comicvine_id'),
				'title': f"{matching_result['title']} ({matching_result['year']})" if matching_result else None,
				'link': matching_result.get('comicvine_info')
			}
			cv_to_data.append((
				cv_data,
				f['data']
			))
			f['cv'] = cv_data
			del f['data']

	unimported_files.sort(key=lambda e: e['file_title'])

	return unimported_files

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
