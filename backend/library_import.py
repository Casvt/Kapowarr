#-*- coding: utf-8 -*-

import logging
from asyncio import create_task, gather, run
from os.path import basename, dirname, isfile, join, splitext
from typing import Dict, Iterator, List, Sequence

from aiohttp import ClientSession

from backend.comicvine import ComicVine
from backend.custom_exceptions import VolumeAlreadyAdded
from backend.db import get_db
from backend.file_extraction import (extract_filename_data, image_extensions,
                                     supported_extensions)
from backend.files import (delete_empty_folders, find_lowest_common_folder,
                           folder_is_inside_folder, list_files, rename_file)
from backend.helpers import (CVFileMapping, DictKeyedDict, FilenameData,
                             batched, create_range)
from backend.matching import _match_title, _match_year
from backend.naming import mass_rename
from backend.root_folders import RootFolders
from backend.volumes import Library, Volume, scan_files


async def __search_matches(
	datas: Sequence[FilenameData],
	only_english: bool
) -> DictKeyedDict:

	comicvine = ComicVine()
	results = DictKeyedDict()
	async with ClientSession() as session:
		data_titles = {d['series'].lower() for d in datas}
		tasks = [
			create_task(comicvine.search_volumes_async(session, series))
			for series in data_titles
		]
		responses = await gather(*tasks)
		title_to_response = dict(zip(data_titles, responses))

		for data in datas:
			# Find all matches
			matching_results: Dict[str, List[dict]] = {
				'year': [],
				'volume_number': []
			}
			for result in title_to_response[data['series'].lower()]:
				if (_match_title(data['series'], result['title'])
				and (
					(only_english and not result['translated'])
					or
					(not only_english)
				)):
					if _match_year(data['year'], result['year']):
						matching_results['year'].append(result)

					elif (
						data['volume_number'] is not None
						and result['volume_number'] is not None
						and result['volume_number'] == data['volume_number']
					):
						matching_results['volume_number'].append(result)

			# Sort matches
			matching_results['year'].sort(
				key=lambda r: int(not data['year'] == r['year'])
			)
			matching_result = next(
				iter(
					matching_results['year'] or matching_results['volume_number']
				),
				{}
			)

			if matching_result:
				title = f"{matching_result['title']} ({matching_result['year']})"
			else:
				title = None

			results[data] = {
				'id': matching_result.get('comicvine_id'),
				'title': title,
				'issue_count': matching_result.get('issue_count'),
				'link': matching_result.get('comicvine_info')
			}

		return results

def propose_library_import(
	limit: int = 20,
	limit_parent_folder: bool = False,
	only_english: bool = True
) -> List[dict]:
	"""Get list of unimported files
	and their suggestion for a matching volume on CV.

	Args:
		limit (int, optional): The max amount of folders to scan.
			Defaults to 20.

		limit_parent_folder (bool, optional): Base the folder limit on
		parent folder, not folder. Useful if each issue has their own sub-folder.
			Defaults to False.

		only_english (bool, optional): Only match with english releases.
			Defaults to True.

	Returns:
		List[dict]: The list of files and their matches.
	"""
	logging.info('Loading library import')

	# Get all files in all root folders
	root_folders = RootFolders().get_all()
	all_files: List[str] = []
	for f in root_folders:
		all_files += list_files(f['folder'], supported_extensions)

	# Get imported files
	cursor = get_db()
	imported_files = set(
		f[0] for f in cursor.execute(
			"SELECT filepath FROM files"
		)
	)

	# Filter away imported files and apply limit
	limited_files = []
	folders = set()
	image_folders = set()
	for f in all_files:
		if f in imported_files:
			continue

		if f.endswith(image_extensions):
			f = dirname(f)
			if f in image_folders:
				continue
			image_folders.add(f)

		if limit_parent_folder:
			folders.add(dirname(dirname(f)))
		else:
			folders.add(dirname(f))

		if len(folders) > limit:
			break

		limited_files.append(f)

	# List with tuples. First entry is efd,
	# second is all matching files for that efd.
	unimported_files = DictKeyedDict()
	for f in limited_files:
		efd = extract_filename_data(f, prefer_folder_year=True)
		del efd['issue_number'] # type: ignore

		(unimported_files
			.setdefault(efd, [])
			.append(f))
	logging.debug(f'File groupings: {unimported_files}')

	# Find a match for the files on CV
	result: List[dict] = []
	uf: Iterator[FilenameData] = unimported_files.keys()
	group_number = 1
	for uf_batch in batched(
		sorted(uf, key=lambda f: (
			f['series'],
			create_range(f['volume_number'] or 0)[0],
			f['year'] or 0
		)),
		10
	):
		group_to_cv = run(__search_matches(
			uf_batch,
			only_english
		))
		for group_data, search_result in group_to_cv.items():
			result += [
				{
					'filepath': f,
					'file_title': (
						splitext(basename(f))[0]
						if isfile(f) else
						basename(f)
					),
					'cv': search_result,
					'group_number': group_number
				}
				for f in unimported_files[group_data]
			]
			group_number += 1

	result.sort(key=lambda e: (e['group_number'], e['file_title']))

	return result

def import_library(
	matches: List[CVFileMapping],
	rename_files: bool=False
) -> None:
	"""Add volume to library and import linked files

	Args:
		matches (List[CVFileMapping]): List of dicts.
		The key `id` should supply the CV id of the volume
		and `filepath` the linked file.

		rename_files (bool, optional): Should Kapowarr trigger a rename
		after importing files?
			Defaults to False.
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
		if not rename_files:
			volume_folder = find_lowest_common_folder(files)
		else:
			volume_folder = None

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

		if rename_files:
			# Put files in volume folder
			vf: str = Volume(volume_id)['folder']
			new_files = []
			for f in files:
				if f.endswith(image_extensions):
					target_f = join(vf, basename(dirname(f)), basename(f))
				else:
					target_f = join(vf, basename(f))

				if folder_is_inside_folder(f, target_f):
					new_files.append(f)
					continue

				rename_file(f, target_f)
				new_files.append(target_f)
				delete_empty_folders(dirname(f), root_folder['folder'])

			scan_files(volume_id)

			# Trigger rename
			mass_rename(volume_id, filepath_filter=new_files)

		else:
			scan_files(volume_id)

	return
