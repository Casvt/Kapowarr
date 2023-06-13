#-*- coding: utf-8 -*-

import logging
from typing import Any, Tuple

from flask import Blueprint, Flask, request, send_file

from backend.blocklist import (add_to_blocklist, delete_blocklist,
                               delete_blocklist_entry, get_blocklist,
                               get_blocklist_entry)
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
                                       TaskNotFound, VolumeAlreadyAdded,
                                       VolumeDownloadedFor, VolumeNotFound)
from backend.db import close_db
from backend.download import (DownloadHandler, credentials,
                              delete_download_history, get_download_history)
from backend.naming import mass_rename, preview_mass_rename
from backend.root_folders import RootFolders
from backend.search import manual_search
from backend.settings import Settings, about_data, blocklist_reasons
from backend.tasks import (TaskHandler, delete_task_history, get_task_history,
                           get_task_planning, task_library)
from backend.volumes import Library, search_volumes, ui_vars

api = Blueprint('api', __name__)
root_folders = RootFolders()
library = Library()
settings = Settings()

# Create handlers
handler_context = Flask('handler')
handler_context.teardown_appcontext(close_db)
download_handler = DownloadHandler(handler_context)
task_handler = TaskHandler(handler_context, download_handler)

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
				TaskNotFound, VolumeAlreadyAdded,
				VolumeDownloadedFor, VolumeNotFound) as e:
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
			if not value == settings.get_settings()['api_key']:
				raise InvalidKeyValue(key, value)

		elif key == 'password':
			auth_password = settings.get_settings().get('auth_password', '')
			if auth_password != '' and value != auth_password:
				raise InvalidKeyValue(key, value)

		elif key == 'sort':
			if not value in library.sorting_orders.keys():
				raise InvalidKeyValue(key, value)

		elif key in ('root_folder_id', 'offset'):
			try:
				value = int(value)
			except (ValueError, TypeError):
				raise InvalidKeyValue(key, value)

		elif key == 'reason_id':
			value = int(value)
			if not value in blocklist_reasons:
				raise InvalidKeyValue(key, value)

		elif key in ('monitor', 'delete_folder', 'issues_as_volumes'):
			if value == 'true':
				value = True
			elif value == 'false':
				value = False
			else:
				raise InvalidKeyValue(key, value)
			
	else:
		# Default value
		if key == 'sort':
			value = 'title'

		elif key == 'monitor':
			value = True

		elif key == 'delete_folder':
			value = False

		elif key == 'offset':
			value = 0

		elif key == 'issues_as_volumes':
			value = False

	return value

#=====================
# Authentication function and endpoints
#=====================
def auth(method):
	"""Used as decorator and, if applied to route, restricts the route to authorized users only
	"""
	def wrapper(*args,**kwargs):
		if not (
			request.method == 'GET' and request.path in ('/api/system/tasks', '/api/activity/queue')
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
	try:
		if settings.get_settings()['auth_password']:
			extract_key(request, 'password')
	except InvalidKeyValue:
		logging.warning(f'Login attempt failed from {request.remote_addr}')
		return return_api({}, 'PasswordInvalid', 401)
	except KeyNotFound:
		return return_api({}, 'PasswordInvalid', 401)
	else:
		logging.info(f'Login attempt successful from {request.remote_addr}')
		return return_api({'api_key': settings.get_settings()['api_key']})

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
		task = extract_key(request, 'cmd')

		if task.action in ('auto_search_issue', 'auto_search', 'refresh_and_scan', 'unzip'):
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
	if request.method == 'GET':
		result = settings.get_settings()
		return return_api(result)

	elif request.method == 'PUT':
		data = request.get_json()
		result = settings.set_settings(data)
		return return_api(result)

	elif request.method == 'DELETE':
		key = extract_key(request, 'key')
		result = settings.reset_setting(key)
		return return_api(result)

@api.route('/settings/api_key', methods=['POST'])
@error_handler
@auth
def api_settings_api_key():
	result = settings.generate_api_key()
	return return_api(result)

@api.route('/settings/servicepreference', methods=['GET', 'PUT'])
@error_handler
@auth
def api_settings_service_preference():
	if request.method == 'GET':
		result = settings.get_service_preference()
		return return_api(result)
	
	elif request.method == 'PUT':
		data = request.get_json()
		if not 'order' in data:
			raise KeyNotFound('order')
		if not isinstance(data['order'], list):
			raise InvalidKeyValue('order', data['order'])
		current_order = settings.get_service_preference()
		for entry in data['order']:
			if not entry in current_order:
				raise InvalidKeyValue('order', data['order'])

		settings.set_service_preference(data['order'])
		return return_api({})

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
		if folder is None: raise KeyNotFound('folder')
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
# Library + Volumes
#=====================
@api.route('/volumes/search', methods=['GET'])
@error_handler
@auth
def api_volumes_search():
	query = extract_key(request, 'query')
	search_results = search_volumes(query)
	return return_api(search_results)

@api.route('/volumes', methods=['GET','POST'])
@error_handler
@auth
def api_volumes():
	if request.method == 'GET':
		query = extract_key(request, 'query', False)
		sort = extract_key(request, 'sort', False)
		if query:
			volumes = library.search(query, sort)
		else:
			volumes = library.get_volumes(sort)

		return return_api(volumes)

	elif request.method == 'POST':
		comicvine_id = extract_key(request, 'comicvine_id')
		root_folder_id = extract_key(request, 'root_folder_id')
		monitor = extract_key(request, 'monitor', False)
		issues_as_volumes = extract_key(request, 'issues_as_volumes', False)

		volume_id = library.add(comicvine_id, root_folder_id, monitor, issues_as_volumes)
		volume_info = library.get_volume(volume_id).get_info()
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
		volume_info = volume.get_info()
		return return_api(volume_info)

	elif request.method == 'PUT':
		edit_info = request.get_json()
		result = volume.edit(edit_info)
		return return_api(result)

	elif request.method == 'DELETE':
		delete_folder = extract_key(request, 'delete_folder')
		volume.delete(delete_folder=delete_folder)
		return return_api({})

@api.route('/volumes/<int:id>/cover', methods=['GET'])
@error_handler
@auth
def api_volume_cover(id: int):
	cover = library.get_volume(id).get_cover()
	return send_file(cover, 'image/jpeg'), 200

@api.route('/issues/<int:id>', methods=['GET','PUT'])
@error_handler
@auth
def api_issues(id: int):
	issue = library.get_issue(id)

	if request.method == 'GET':
		result = issue.get_info()
		return return_api(result)

	elif request.method == 'PUT':
		edit_info: dict = request.get_json()
		monitored = edit_info.get('monitor')
		if monitored:
			issue.monitor()
		else:
			issue.unmonitor()

		result = issue.get_info()
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
		mass_rename(id)
		return return_api(None)

@api.route('/issues/<int:id>/rename', methods=['GET','POST'])
@error_handler
@auth
def api_rename_issue(id: int):
	volume_id = library.get_issue(id).get_info()['volume_id']

	if request.method == 'GET':
		result = preview_mass_rename(volume_id, id)
		return return_api(result)
		
	elif request.method == 'POST':
		mass_rename(volume_id, id)
		return return_api(None)

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
	link = extract_key(request, 'link')
	library.get_volume(id)
	result = download_handler.add(link, id)
	return return_api(result, code=201)

@api.route('/issues/<int:id>/manualsearch', methods=['GET'])
@error_handler
@auth
def api_issue_manual_search(id: int):
	issue_info = library.get_issue(id).get_info()
	result = manual_search(
		issue_info['volume_id'],
		id
	)
	return return_api(result)

@api.route('/issues/<int:id>/download', methods=['POST'])
@error_handler
@auth
def api_issue_download(id: int):
	link = extract_key(request, 'link')
	issue_info = library.get_issue(id).get_info()
	result = download_handler.add(link, issue_info['volume_id'], id)
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
		reason_id = extract_key(request, 'reason_id')
		result = add_to_blocklist(link, reason_id)
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
