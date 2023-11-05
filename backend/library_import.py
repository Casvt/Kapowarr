#-*- coding: utf-8 -*-

import logging
from asyncio import create_task, gather, run
from os.path import basename, commonpath, dirname, join, splitext
from shutil import Error, move
from typing import Dict, List, Tuple, Union

from aiohttp import ClientSession

from backend.comicvine import ComicVine
from backend.custom_exceptions import VolumeAlreadyAdded
from backend.db import get_db
from backend.files import (_list_files, delete_empty_folders,
                           extract_filename_data, image_extensions, scan_files,
                           supported_extensions)
from backend.helpers import batched
from backend.naming import mass_rename
from backend.root_folders import RootFolders
from backend.search import _check_matching_titles
from backend.volumes import Library, Volume


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

def __find_lowest_common_folder(files: List[str]) -> str:
	"""Find the lowest folder that is shared between the files

	Args:
		files (List[str]): The list of files to find the lowest common folder for

	Returns:
		str: The path of the lowest common folder
	"""
	if len(files) == 1:
		return dirname(files[0])

	return commonpath(files)

def import_library(matches: List[Dict[str, Union[str, int]]], rename_files: bool=False) -> None:
	"""Add volume to library and import linked files

	Args:
		matches (List[Dict[str, Union[str, int]]]): List of dicts.
		The key `id` should supply the CV id of the volume and `filepath` the linked file.
		rename_files (bool, optional): Should Kapowarr trigger a rename after importing files? Defaults to False.
	"""
	logging.info('Starting library import')
	cvid_to_filepath: Dict[int, List[str]] = {}
	for match in matches:
		cvid_to_filepath.setdefault(match['id'], []).append(match['filepath'])
	logging.debug(f'id_to_filepath: {cvid_to_filepath}')

	root_folders = RootFolders().get_all()

	cursor = get_db()
	library = Library()
	for cv_id, files in cvid_to_filepath.items():
		# Find lowest common folder (lcf)
		volume_folder = __find_lowest_common_folder(files) if not rename_files else None

		# Find root folder that media is in
		for root_folder in root_folders:
			if files[0].startswith(root_folder['folder']):
				root_folder_id = root_folder['id']
				break
		else:
			continue

		try:
			volume_id = library.add(
				comicvine_id=str(cv_id),
				root_folder_id=root_folder_id,
				monitor=True,
				volume_folder=volume_folder
			)
			cursor.connection.commit()

		except VolumeAlreadyAdded:
			# The volume is already added but the file is not matched to it
			# (it isn't because otherwise it wouldn't pop up in LI).
			# That would mean that the file is actually not
			# for that volume so skip.
			continue

		volume = Volume(volume_id)
		if rename_files:
			# Put files in volume folder
			vf: str = volume.get_info()['folder']
			new_files = []
			for f in files:
				if f.endswith(image_extensions):
					try:
						new_files.append(move(
							f, join(vf, basename(dirname(f)))
						))
					except Error:
						new_files.append(
							join(vf, basename(dirname(f)), basename(f))
						)
				else:
					try:
						new_files.append(move(f, vf))
					except Error:
						new_files.append(join(vf, basename(f)))

				delete_empty_folders(dirname(f), root_folder['folder'])

			scan_files(volume.get_info())
			
			# Trigger rename
			mass_rename(volume_id, filepath_filter=new_files)

		else:
			scan_files(volume.get_info())

	return
