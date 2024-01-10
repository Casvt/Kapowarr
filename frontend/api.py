#-*- coding: utf-8 -*-

import logging
from typing import Any, Dict, List, Tuple

from flask import Blueprint, Flask, request, send_file

from backend.blocklist import (add_to_blocklist, delete_blocklist,
                               delete_blocklist_entry, get_blocklist,
                               get_blocklist_entry)
from backend.conversion import (get_available_formats, mass_convert,
                                preview_mass_convert)
from backend.custom_exceptions import (BlocklistEntryNotFound,
                                       CredentialAlreadyAdded,
                                       CredentialInvalid, CredentialNotFound,
                                       CredentialSourceNotFound,
                                       CVRateLimitReached, DownloadNotFound,
                                       FolderNotFound, InvalidComicVineApiKey,
                                       InvalidKeyValue, InvalidSettingKey,
                                       InvalidSettingModification,
                                       InvalidSettingValue, IssueNotFound,
                                       KeyNotFound, RootFolderInUse,
                                       RootFolderNotFound, TaskNotDeletable,
                                       TaskNotFound, TorrentClientDownloading,
                                       TorrentClientNotFound,
                                       TorrentClientNotWorking,
                                       VolumeAlreadyAdded, VolumeDownloadedFor,
                                       VolumeNotFound)
from backend.db import close_db
from backend.download_direct_clients import credentials
from backend.download_queue import (DownloadHandler, delete_download_history,
                                    get_download_history)
from backend.download_torrent_clients import TorrentClients, client_types
from backend.enums import BlocklistReason, BlocklistReasonID
from backend.library_import import import_library, propose_library_import
from backend.mass_edit import MassEditorVariables, action_to_func
from backend.naming import (generate_volume_folder_name, mass_rename,
                            preview_mass_rename)
from backend.root_folders import RootFolders
from backend.search import manual_search
from backend.settings import Settings, about_data
from backend.tasks import (Task, TaskHandler, delete_task_history,
                           get_task_history, get_task_planning, task_library)
from backend.volumes import Library, search_volumes

api = Blueprint('api', __name__)
root_folders = RootFolders()
library = Library()

# Create handlers
handler_context = Flask('handler')
handler_context.teardown_appcontext(close_db)
download_handler = DownloadHandler(handler_context)
task_handler = TaskHandler(handler_context, download_handler)
MassEditorVariables.download_handler = download_handler

def return_api(result: Any, error: str=None, code: int=200) -> Tuple[dict, int]:
	return {'error': error, 'result': result}, code

def error_handler(method):
	"""Used as decodator. Catches the errors that can occur in the endpoint and returns the correct api error
	"""
	def wrapper(*args, **kwargs):
		try:
			return method(*args, **kwargs)

		except (BlocklistEntryNotFound,
			CredentialAlreadyAdded,
			CredentialInvalid, CredentialNotFound,
			CredentialSourceNotFound,
			CVRateLimitReached, DownloadNotFound,
			FolderNotFound, InvalidComicVineApiKey,
			InvalidKeyValue, InvalidSettingKey,
			InvalidSettingModification,
			InvalidSettingValue, IssueNotFound,
			KeyNotFound, RootFolderInUse,
			RootFolderNotFound, TaskNotDeletable,
			TaskNotFound, TorrentClientDownloading,
			TorrentClientNotFound,
			TorrentClientNotWorking,
			VolumeAlreadyAdded, VolumeDownloadedFor,
			VolumeNotFound
		) as e:
			return return_api(**e.api_response)
	
	wrapper.__name__ = method.__name__
	return wrapper

def extract_key(request, key: str, check_existence: bool=True) -> Any:
	"""Extract and format a value of a parameter from a request

	Args:
		request (Request): The request from which to get the values.
		key (str): The key of which to get and format the value.
		check_existence (bool, optional): Require the key to be given in the request. Defaults to True.

	Raises:
		KeyNotFound: The key is not found in the request.
		InvalidKeyValue: The value of a key is invalid.
		TaskNotFound: The task was not found

	Returns:
		Any: The formatted value of the key.
	"""	
	value: str = request.values.get(key)
	if check_existence and value is None:
		raise KeyNotFound(key)

	if value is not None:
		# Check value
		if key in ('volume_id', 'issue_id'):
			try:
				value = int(value)
				if key == 'volume_id':
					library.get_volume(value)
				else:
					library.get_issue(value)
			except (ValueError, TypeError):
				raise InvalidKeyValue(key, value)

		elif key == 'cmd':
			value = task_library.get(value)
			if value is None:
				raise TaskNotFound

		elif key == 'api_key':
			if not value == Settings()['api_key']:
				raise InvalidKeyValue(key, value)

		elif key == 'sort':
			if not value in library.sorting_orders:
				raise InvalidKeyValue(key, value)

		elif key == 'filter':
			if not value in library.filters and value:
				raise InvalidKeyValue(key, value)
			value = value or None

		elif key in ('root_folder_id', 'root_folder', 'offset', 'limit'):
			try:
				value = int(value)
			except (ValueError, TypeError):
				raise InvalidKeyValue(key, value)

		elif key == 'reason_id':
			try:
				value = BlocklistReason[
					BlocklistReasonID(int(value)).name
				]
			except ValueError:
				raise InvalidKeyValue(key, value)

		elif key in ('monitor', 'delete_folder', 'rename_files', 'only_english'):
			if value == 'true':
				value = True
			elif value == 'false':
				value = False
			else:
				raise InvalidKeyValue(key, value)

		elif key == 'type':
			if not value in client_types:
				raise InvalidKeyValue(key, value)

	else:
		# Default value
		if key == 'sort':
			value = 'title'

		elif key == 'filter':
			value = None

		elif key == 'monitor':
			value = True

		elif key == 'delete_folder':
			value = False

		elif key == 'offset':
			value = 0

		elif key == 'rename_files':
			value = False

		elif key == 'limit':
			value = 20

		elif key == 'only_english':
			value = True

	return value

#=====================
# Authentication function and endpoints
#=====================
def auth(method):
	"""Used as decorator and, if applied to route, restricts the route to authorized users only
	"""
	def wrapper(*args,**kwargs):
		if not (
			request.method == 'GET'
			and (request.path in ('/api/system/tasks', '/api/activity/queue')
				or request.path.endswith('/cover'))
		):
			logging.debug(f'{request.method} {request.path}')
		try:
			extract_key(request, 'api_key')
		except (KeyNotFound, InvalidKeyValue):
			return return_api({}, 'ApiKeyInvalid', 401)

		result = method(*args, **kwargs)
		if result[1] > 300:
			logging.debug(f'{request.method} {request.path} {result[1]} {result[0]}')
		return result

	wrapper.__name__ = method.__name__
	return wrapper

@api.route('/auth', methods=['POST'])
def api_auth():
	settings = Settings()

	ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

	if settings['auth_password']:
		given_password = request.get_json().get('password')
		if given_password is None:
			return return_api({}, 'PasswordInvalid', 401)

		auth_password = settings['auth_password']
		if auth_password is not None and given_password != auth_password:
			logging.warning(f'Login attempt failed from {ip}')
			return return_api({}, 'PasswordInvalid', 401)

	logging.info(f'Login attempt successful from {ip}')
	return return_api({'api_key': settings['api_key']})

@api.route('/auth/check', methods=['POST'])
@error_handler
@auth
def api_auth_check():
	return return_api({})

#=====================
# Tasks
#=====================
@api.route('/system/about', methods=['GET'])
@error_handler
@auth
def api_about():
	return return_api(about_data)

@api.route('/system/tasks', methods=['GET','POST'])
@error_handler
@auth
def api_tasks():
	if request.method == 'GET':
		tasks = task_handler.get_all()
		return return_api(tasks)

	elif request.method == 'POST':
		task: Task = extract_key(request, 'cmd')

		if task.action in ('auto_search_issue', 'auto_search', 'refresh_and_scan'):
			volume_id = extract_key(request, 'volume_id')

			if task.action in ('auto_search_issue',):
				issue_id = extract_key(request, 'issue_id')
				task_instance = task(volume_id, issue_id)
			else:
				task_instance = task(volume_id)
		else:
			task_instance = task()

		result = task_handler.add(task_instance)
		return return_api({'id': result}, code=201)

@api.route('/system/tasks/history', methods=['GET','DELETE'])
@error_handler
@auth
def api_task_history():
	if request.method == 'GET':
		offset = extract_key(request, 'offset', False)
		tasks = get_task_history(offset)
		return return_api(tasks)
	
	elif request.method == 'DELETE':
		delete_task_history()
		return return_api({})

@api.route('/system/tasks/planning', methods=['GET'])
@error_handler
@auth
def api_task_planning():
	result = get_task_planning()
	return return_api(result)

@api.route('/system/tasks/<int:task_id>', methods=['GET','DELETE'])
@error_handler
@auth
def api_task(task_id: int):
	if request.method == 'GET':
		task = task_handler.get_one(task_id)
		return return_api(task)
		
	elif request.method == 'DELETE':
		task_handler.remove(task_id)
		return return_api({})

#=====================
# Settings
#=====================
@api.route('/settings', methods=['GET','PUT','DELETE'])
@error_handler
@auth
def api_settings():
	settings = Settings()
	if request.method == 'GET':
		result = settings.get_all()
		return return_api(result)

	elif request.method == 'PUT':
		data = request.get_json()
		settings.update(data)
		return return_api(settings.get_all())

	elif request.method == 'DELETE':
		key = extract_key(request, 'key')
		settings.reset(key)
		return return_api(settings.get_all())

@api.route('/settings/api_key', methods=['POST'])
@error_handler
@auth
def api_settings_api_key():
	settings = Settings()
	settings.generate_api_key()
	return return_api(settings.get_all())

@api.route('/settings/availableformats', methods=['GET'])
@error_handler
@auth
def api_settings_available_formats():
	result = list(get_available_formats())
	return return_api(result)

@api.route('/rootfolder', methods=['GET','POST'])
@error_handler
@auth
def api_rootfolder():
	if request.method == 'GET':
		result = root_folders.get_all()
		return return_api(result)

	elif request.method == 'POST':
		data: dict = request.get_json()
		folder = data.get('folder')
		if folder is None:
			raise KeyNotFound('folder')
		root_folder = root_folders.add(folder)
		return return_api(root_folder, code=201)

@api.route('/rootfolder/<int:id>', methods=['GET','DELETE'])
@error_handler
@auth
def api_rootfolder_id(id: int):
	if request.method == 'GET':
		root_folder = root_folders.get_one(id)
		return return_api(root_folder)

	elif request.method == 'DELETE':
		root_folders.delete(id)
		return return_api({})

#=====================
# Library Import
#=====================
@api.route('/libraryimport', methods=['GET', 'POST'])
@error_handler
@auth
def api_library_import():
	if request.method == 'GET':
		limit = extract_key(request, 'limit', check_existence=False)
		only_english = extract_key(request, 'only_english', check_existence=False)
		result = propose_library_import(limit, only_english)
		return return_api(result)
	
	elif request.method == 'POST':
		data = request.get_json()
		rename_files = extract_key(request, 'rename_files', False)

		if (
			not isinstance(data, list)
			or not all(
				isinstance(e, dict) and 'filepath' in e and 'id' in e
				for e in data
			)
		):
			raise InvalidKeyValue

		import_library(data, rename_files)
		return return_api({}, code=201)

#=====================
# Library + Volumes
#=====================
@api.route('/volumes/search', methods=['GET', 'POST'])
@error_handler
@auth
def api_volumes_search():
	if request.method == 'GET':
		query = extract_key(request, 'query')
		search_results = search_volumes(query)
		return return_api(search_results)
	
	elif request.method == 'POST':
		data = request.get_json()
		for key in ('comicvine_id', 'title', 'year', 'volume_number', 'publisher'):
			if not key in data:
				raise KeyNotFound(key)
		folder = generate_volume_folder_name(-1, data)
		return return_api({'folder': folder})

@api.route('/volumes', methods=['GET','POST'])
@error_handler
@auth
def api_volumes():
	if request.method == 'GET':
		query = extract_key(request, 'query', False)
		sort = extract_key(request, 'sort', False)
		filter = extract_key(request, 'filter', False)
		if query:
			volumes = library.search(query, sort, filter)
		else:
			volumes = library.get_volumes(sort, filter)

		return return_api(volumes)

	elif request.method == 'POST':
		data: dict = request.get_json()

		comicvine_id = data.get('comicvine_id')
		if comicvine_id is None: raise KeyNotFound('comicvine_id')
		root_folder_id = data.get('root_folder_id')
		if root_folder_id is None: raise KeyNotFound('root_folder_id')
		monitor = data.get('monitor', True)
		volume_folder = data.get('volume_folder') or None

		volume_id = library.add(comicvine_id, root_folder_id, monitor, volume_folder)
		volume_info = library.get_volume(volume_id).get_public_keys()
		return return_api(volume_info, code=201)

@api.route('/volumes/stats', methods=['GET'])
@error_handler
@auth
def api_volumes_stats():
	result = library.get_stats()
	return return_api(result)

@api.route('/volumes/<int:id>', methods=['GET','PUT','DELETE'])
@error_handler
@auth
def api_volume(id: int):
	volume = library.get_volume(id)

	if request.method == 'GET':
		volume_info = volume.get_public_keys()
		return return_api(volume_info)

	elif request.method == 'PUT':
		edit_info = request.get_json()
		result = volume.update(edit_info)
		return return_api(result)

	elif request.method == 'DELETE':
		delete_folder = extract_key(request, 'delete_folder')
		volume.delete(delete_folder=delete_folder)
		return return_api({})

@api.route('/volumes/<int:id>/cover', methods=['GET'])
@error_handler
@auth
def api_volume_cover(id: int):
	cover = library.get_volume(id)['cover']
	return send_file(cover, 'image/jpeg'), 200

@api.route('/issues/<int:id>', methods=['GET','PUT'])
@error_handler
@auth
def api_issues(id: int):
	issue = library.get_issue(id)

	if request.method == 'GET':
		result = issue.get_public_keys()
		return return_api(result)

	elif request.method == 'PUT':
		edit_info: dict = request.get_json()
		monitored = edit_info.get('monitored')
		if monitored is not None:
			issue['monitored'] = bool(monitored)

		result = issue.get_public_keys()
		return return_api(result)

#=====================
# Renaming
#=====================
@api.route('/volumes/<int:id>/rename', methods=['GET','POST'])
@error_handler
@auth
def api_rename(id: int):
	library.get_volume(id)

	if request.method == 'GET':
		result = preview_mass_rename(id)
		return return_api(result)
		
	elif request.method == 'POST':
		filepath_filter = request.get_json(silent=True)
		mass_rename(id, filepath_filter=filepath_filter)
		return return_api({})

@api.route('/issues/<int:id>/rename', methods=['GET','POST'])
@error_handler
@auth
def api_rename_issue(id: int):
	volume_id = library.get_issue(id)['volume_id']

	if request.method == 'GET':
		result = preview_mass_rename(volume_id, id)
		return return_api(result)
		
	elif request.method == 'POST':
		filepath_filter = request.get_json(silent=True)
		mass_rename(volume_id, id, filepath_filter=filepath_filter)
		return return_api({})

#=====================
# File Conversion
#=====================
@api.route('/volumes/<int:id>/convert', methods=['GET','POST'])
@error_handler
@auth
def api_convert(id: int):
	library.get_volume(id)

	if request.method == 'GET':
		result = preview_mass_convert(id)
		return return_api(result)
		
	elif request.method == 'POST':
		files = request.get_json(silent=True) or []
		mass_convert(id, files=files)
		return return_api({})

@api.route('/issues/<int:id>/convert', methods=['GET','POST'])
@error_handler
@auth
def api_convert_issue(id: int):
	volume_id = library.get_issue(id)['volume_id']

	if request.method == 'GET':
		result = preview_mass_convert(volume_id, id)
		return return_api(result)
		
	elif request.method == 'POST':
		files = request.get_json(silent=True) or []
		mass_convert(volume_id, id, files=files)
		return return_api({})

#=====================
# Manual search + Download
#=====================
@api.route('/volumes/<int:id>/manualsearch', methods=['GET'])
@error_handler
@auth
def api_volume_manual_search(id: int):
	library.get_volume(id)
	result = manual_search(id)
	return return_api(result)

@api.route('/volumes/<int:id>/download', methods=['POST'])
@error_handler
@auth
def api_volume_download(id: int):
	library.get_volume(id)
	link = extract_key(request, 'link')
	result = download_handler.add(link, id)
	return return_api(result, code=201)

@api.route('/issues/<int:id>/manualsearch', methods=['GET'])
@error_handler
@auth
def api_issue_manual_search(id: int):
	volume_id = library.get_issue(id)['volume_id']
	result = manual_search(
		volume_id,
		id
	)
	return return_api(result)

@api.route('/issues/<int:id>/download', methods=['POST'])
@error_handler
@auth
def api_issue_download(id: int):
	volume_id = library.get_issue(id)['volume_id']
	link = extract_key(request, 'link')
	result = download_handler.add(link, volume_id, id)
	return return_api(result, code=201)

@api.route('/activity/queue', methods=['GET'])
@error_handler
@auth
def api_downloads():
	result = download_handler.get_all()
	return return_api(result)

@api.route('/activity/queue/<int:download_id>', methods=['GET','DELETE'])
@error_handler
@auth
def api_delete_download(download_id: int):
	if request.method == 'GET':
		result = download_handler.get_one(download_id)
		return return_api(result)

	elif request.method == 'DELETE':
		download_handler.remove(download_id)
		return return_api({})

@api.route('/activity/history', methods=['GET','DELETE'])
@error_handler
@auth
def api_download_history():
	if request.method == 'GET':
		offset = extract_key(request, 'offset', False)
		result = get_download_history(offset)
		return return_api(result)

	elif request.method == 'DELETE':
		delete_download_history()
		return return_api({})

@api.route('/activity/folder', methods=['DELETE'])
@error_handler
@auth
def api_empty_download_folder():
	download_handler.empty_download_folder()
	return return_api({})

#=====================
# Blocklist
#=====================
@api.route('/blocklist', methods=['GET', 'POST', 'DELETE'])
@error_handler
@auth
def api_blocklist():
	if request.method == 'GET':
		offset = extract_key(request, 'offset', False)
		result = get_blocklist(offset)
		return return_api(result)
	
	elif request.method == 'POST':
		link = extract_key(request, 'link')
		reason = extract_key(request, 'reason_id')
		result = add_to_blocklist(link, reason)
		return return_api(result, code=201)
	
	elif request.method == 'DELETE':
		delete_blocklist()
		return return_api({})

@api.route('/blocklist/<int:id>', methods=['GET', 'DELETE'])
@error_handler
@auth
def api_blocklist_entry(id: int):
	if request.method == 'GET':
		result = get_blocklist_entry(id)
		return return_api(result)

	elif request.method == 'DELETE':
		delete_blocklist_entry(id)
		return return_api({})

#=====================
# Credentials
#=====================
@api.route('/credentials', methods=['GET', 'POST'])
@error_handler
@auth
def api_credentials():
	if request.method == 'GET':
		result = credentials.get_all()
		return return_api(result)
	
	elif request.method == 'POST':
		source = extract_key(request, 'source')
		email = extract_key(request, 'email')
		password = extract_key(request, 'password')
		result = credentials.add(source, email, password)
		return return_api(result, code=201)

@api.route('/credentials/open', methods=['GET'])
@error_handler
@auth
def api_open_credentials():
	result = credentials.get_open()
	return return_api(result)
	
@api.route('/credentials/<int:id>', methods=['GET', 'DELETE'])
@error_handler
@auth
def api_credential(id: int):
	if request.method == 'GET':
		result = credentials.get_one(id)
		return return_api(result)
	
	elif request.method == 'DELETE':
		credentials.delete(id)
		return return_api({})

#=====================
# Torrent Clients
#=====================
@api.route('/torrentclients', methods=['GET', 'POST'])
@error_handler
@auth
def api_torrent_clients():
	if request.method == 'GET':
		result = TorrentClients.get_clients()
		return return_api(result)

	elif request.method == 'POST':
		data: dict = request.get_json()
		data = {
			k: data.get(k)
			for k in ('type',
					'title', 'base_url',
					'username', 'password',
					'api_token'
			)
		}
		result = TorrentClients.add(**data).todict()
		return return_api(result, code=201)

@api.route('/torrentclients/options', methods=['GET'])
@error_handler
@auth
def api_torrent_clients_keys():
	result = {k: v._tokens for k, v in client_types.items()}
	return return_api(result)

@api.route('/torrentclients/test', methods=['POST'])
@error_handler
@auth
def api_torrent_clients_test():
	data: dict = request.get_json()
	data = {
		k: data.get(k)
		for k in ('type', 'base_url',
				'username', 'password',
				'api_token'
		)
	}
	result = TorrentClients.test(**data)
	return return_api({'result': result})

@api.route('/torrentclients/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@error_handler
@auth
def api_torrent_client(id: int):
	client = TorrentClients.get_client(id)

	if request.method == 'GET':
		result = client.todict()
		return return_api(result)

	elif request.method == 'PUT':
		data: dict = request.get_json()
		data = {
			k: data.get(k)
			for k in ('title', 'base_url',
					'username', 'password',
					'api_token'
			)
		}
		result = client.edit(data)
		return return_api(result)

	elif request.method == 'DELETE':
		client.delete()
		return return_api({})

#=====================
# Torrent Clients
#=====================
@api.route('/masseditor', methods=['POST'])
@error_handler
@auth
def api_mass_editor():
	data = request.get_json()
	if not isinstance(data, dict):
		raise InvalidKeyValue('body', data)
	if not 'volume_ids' in data:
		raise KeyNotFound('volume_ids')
	if not 'action' in data:
		raise KeyNotFound('action')

	action: str = data['action']
	volume_ids: List[int] = data['volume_ids']
	args: Dict[str, Any] = data.get('args', {})

	if not (
		isinstance(volume_ids, list)
		and all(isinstance(v, int) for v in volume_ids)
	):
		raise InvalidKeyValue('volume_ids', volume_ids)

	if not action in action_to_func:
		raise InvalidKeyValue('action', action)

	if not isinstance(args, dict):
		raise InvalidKeyValue('args', args)

	action_to_func[action](volume_ids, **args)
	return return_api({})
