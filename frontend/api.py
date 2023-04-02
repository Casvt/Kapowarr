#-*- coding: utf-8 -*-

import logging
from typing import Any

from flask import Blueprint, Flask, request, send_file

from backend.blocklist import (add_to_blocklist, delete_blocklist,
                               delete_blocklist_entry, get_blocklist,
                               get_blocklist_entry)
from backend.custom_exceptions import (BlocklistEntryNotFound,
                                       DownloadNotFound, FolderNotFound,
                                       InvalidComicVineApiKey, InvalidKeyValue,
                                       InvalidSettingKey,
                                       InvalidSettingModification,
                                       InvalidSettingValue, IssueNotFound,
                                       KeyNotFound, RootFolderInUse,
                                       RootFolderNotFound, TaskNotDeletable,
                                       TaskNotFound, VolumeAlreadyAdded,
                                       VolumeNotFound)
from backend.db import __DATABASE_VERSION__, DBConnection, close_db, get_db
from backend.download import (DownloadHandler, delete_download_history,
                              get_download_history)
from backend.files import folder_path
from backend.naming import mass_rename, preview_mass_rename
from backend.root_folders import RootFolders
from backend.search import manual_search
from backend.settings import Settings, blocklist_reasons, private_settings
from backend.tasks import (TaskHandler, delete_task_history, get_task_history,
                           task_library)
from backend.volumes import Library, search_volumes

api = Blueprint('api', __name__)
root_folders = RootFolders()
library = Library()
settings = Settings()

#create handlers
handler_context = Flask('handler')
handler_context.teardown_appcontext(close_db)
download_handler = DownloadHandler(handler_context)
task_handler = TaskHandler(handler_context, download_handler)

def extract_key(request, key: str, check_existence: bool=True) -> Any:
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

		elif key in ('monitor', 'delete_folder'):
			if value == 'true':
				value == True
			elif value == 'false':
				value == False
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

	return value

#=====================
# Authentication function and endpoints
#=====================
def auth(method):
	"""Used as decorator and, if applied to route, restricts the route to authorized users only
	"""
	def wrapper(*args,**kwargs):
		logging.debug(f'{request.method} {request.path}')
		try:
			extract_key(request, 'api_key')
		except (KeyNotFound, InvalidKeyValue):
			return {'error': 'ApiKeyInvalid', 'result': {}}, 401

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
		return {'error': 'PasswordInvalid', 'result': {}}, 401
	except KeyNotFound:
		return {'error': 'PasswordInvalid', 'result': {}}, 401
	else:
		logging.info(f'Login attempt successful from {request.remote_addr}')
		return {'error': None, 'result': {'api_key': settings.get_settings()['api_key']}}, 200

@api.route('/auth/check', methods=['POST'])
@auth
def api_auth_check():
	return {'error': None, 'result': {}}, 200

#=====================
# Tasks
#=====================
@api.route('/system/about', methods=['GET'])
@auth
def api_about():
	result = {
		'version': private_settings['version'],
		'python_version': private_settings['python_version'],
		'database_version': __DATABASE_VERSION__,
		'database_location': DBConnection.file,
		'data_folder': folder_path()
	}
	return {'error': None, 'result': result}, 200

@api.route('/system/tasks', methods=['GET','POST'])
@auth
def api_tasks():
	if request.method == 'GET':
		tasks = task_handler.get_all()
		return {'error': None, 'result': tasks}, 200

	elif request.method == 'POST':
		try:
			task = extract_key(request, 'cmd')
		except (KeyNotFound, TaskNotFound) as e:
			return e.api_response

		if task.action in ('auto_search_issue', 'auto_search', 'refresh_and_scan'):
			try:
				volume_id = extract_key(request, 'volume_id')
			except (KeyNotFound, InvalidKeyValue, VolumeNotFound) as e:
				return e.api_response

			if task.action in ('auto_search_issue',):
				try:
					issue_id = extract_key(request, 'issue_id')
				except (KeyNotFound, InvalidKeyValue, IssueNotFound) as e:
					return e.api_response
					
				task_instance = task(volume_id, issue_id)
			
			else:
				task_instance = task(volume_id)

		else:
			task_instance = task()

		result = task_handler.add(task_instance)
		return {'error': None, 'result': {'id': result}}, 201

@api.route('/system/tasks/history', methods=['GET','DELETE'])
@auth
def api_task_history():
	if request.method == 'GET':
		tasks = get_task_history()
		return {'error': None, 'result': tasks}, 200
	
	elif request.method == 'DELETE':
		delete_task_history()
		return {'error': None, 'result': {}}, 200

@api.route('/system/tasks/planning', methods=['GET'])
@auth
def api_task_planning():
	cursor = get_db('dict')
	
	# Collect what the last time was the tasks were run
	last_run = {}
	for task_name in task_handler.task_intervals.keys():
		run_at = cursor.execute(
			"""
			SELECT
				task_name, run_at
			FROM task_history
			WHERE task_name = ?
			ORDER BY run_at DESC
			LIMIT 1
			""",
			(task_name,)
		).fetchone()
		last_run[run_at['task_name']] = run_at['run_at']

	result = [{
		'task_name': k,
		'display_name': task_library[k].display_title,
		'interval': v['interval'],
		'next_run': v['next_run'],
		'last_run': last_run.get(k)
	} for k, v in task_handler.task_intervals.items()]
	return {'error': None, 'result': result}, 200

@api.route('/system/tasks/<int:task_id>', methods=['GET','DELETE'])
@auth
def api_task(task_id: int):
	if request.method == 'GET':
		try:
			task = task_handler.get_one(task_id)
		except TaskNotFound as e:
			return e.api_response
		else:
			return {'error': None, 'result': task}, 200
		
	elif request.method == 'DELETE':
		try:
			task_handler.remove(task_id)
		except (TaskNotFound, TaskNotDeletable) as e:
			return e.api_response
		else:
			return {'error': None, 'result': {}}, 200

#=====================
# Settings
#=====================
@api.route('/settings', methods=['GET','PUT','DELETE'])
@auth
def api_settings():
	if request.method == 'GET':
		result = settings.get_settings()
		return {'error': None, 'result': result}, 200

	elif request.method == 'PUT':
		data = request.get_json()
		try:
			result = settings.set_settings(data)
		except (InvalidSettingKey, InvalidSettingValue, InvalidSettingModification) as e:
			return e.api_response
		else:
			return {'error': None, 'result': result}, 200

	elif request.method == 'DELETE':
		try:
			key = extract_key(request, 'key')
			result = settings.reset_setting(key)
		except (KeyNotFound, InvalidSettingKey) as e:
			return e.api_response
		else:
			return {'error': None, 'result': result}, 200

@api.route('/settings/api_key', methods=['POST'])
@auth
def api_settings_api_key():
	result = settings.generate_api_key()
	return {'error': 'None', 'result': result}, 200

@api.route('/rootfolder', methods=['GET','POST'])
@auth
def api_rootfolder():
	if request.method == 'GET':
		result = root_folders.get_all()
		return {'error': None, 'result': result}, 200

	elif request.method == 'POST':
		try:
			folder = extract_key(request, 'folder')
			root_folder = root_folders.add(folder)
		except (KeyNotFound, FolderNotFound) as e:
			return e.api_response
		else:
			return {'error': None, 'result': root_folder}, 201

@api.route('/rootfolder/<int:id>', methods=['GET','DELETE'])
@auth
def api_rootfolder_id(id: int):
	if request.method == 'GET':
		try:
			root_folder = root_folders.get_one(id)
		except RootFolderNotFound as e:
			return e.api_response
		else:
			return {'error': None, 'result': root_folder}, 200

	elif request.method == 'DELETE':
		try:
			root_folders.delete(id)
		except (RootFolderNotFound, RootFolderInUse) as e:
			return e.api_response
		else:
			return {'error': None, 'result': {}}, 200

#=====================
# Library + Volumes
#=====================
@api.route('/volumes/search', methods=['GET'])
@auth
def api_volumes_search():
	try:
		query = extract_key(request, 'query')
		search_results = search_volumes(query)
	except (KeyNotFound, InvalidComicVineApiKey) as e:
		return e.api_response
	else:
		return {'error': None, 'result': search_results}, 200

@api.route('/volumes', methods=['GET','POST'])
@auth
def api_volumes():
	if request.method == 'GET':
		try:
			query = extract_key(request, 'query', False)
			sort = extract_key(request, 'sort', False)
			if query:
				volumes = library.search(query)
			else:
				volumes = library.get_volumes(sort)

		except InvalidKeyValue as e:
			return e.api_response
		else:
			return {'error': None, 'result': volumes}, 200

	elif request.method == 'POST':
		try:
			comicvine_id = extract_key(request, 'comicvine_id')
			root_folder_id = extract_key(request, 'root_folder_id')
			monitor = extract_key(request, 'monitor', False)

			volume_id = library.add(comicvine_id, root_folder_id, monitor)
			volume_info = library.get_volume(volume_id).get_info()
		except (KeyNotFound, InvalidKeyValue, VolumeNotFound, VolumeAlreadyAdded, RootFolderNotFound, InvalidComicVineApiKey) as e:
			return e.api_response
		else:
			return {'error': None, 'result': volume_info}, 201

@api.route('/volumes/<int:id>', methods=['GET','PUT','DELETE'])
@auth
def api_volume(id: int):
	try:
		volume = library.get_volume(id)
	except VolumeNotFound as e:
		return e.api_response

	if request.method == 'GET':
		volume_info = volume.get_info()
		return {'error': None, 'result': volume_info}, 200

	elif request.method == 'PUT':
		edit_info = request.get_json()
		try:
			result = volume.edit(edit_info)
		except RootFolderNotFound as e:
			return e.api_response
		
		return {'error': None, 'result': result}, 200

	elif request.method == 'DELETE':
		try:
			delete_folder = extract_key(request, 'delete_folder')
		except InvalidKeyValue as e:
			return e.api_response

		volume.delete(delete_folder=delete_folder)
		return {'error': None, 'result': {}}, 200

@api.route('/volumes/<int:id>/cover', methods=['GET'])
@auth
def api_volume_cover(id: int):
	try:
		cover = library.get_volume(id).get_cover()
		return send_file(cover, 'image/jpeg'), 200
	except VolumeNotFound as e:
		return e.api_response

@api.route('/issues/<int:id>', methods=['GET','PUT'])
@auth
def api_issues(id: int):
	try:
		issue = library.get_issue(id)
	except IssueNotFound as e:
		return e.api_response

	if request.method == 'GET':
		result = issue.get_info()
		return {'error': None, 'result': result}, 200

	elif request.method == 'PUT':
		edit_info = request.get_json()
		monitored = edit_info.get('monitor')
		if monitored == True:
			issue.monitor()
		elif monitored == False:
			issue.unmonitor()

		result = issue.get_info()
		return {'error': None, 'result': result}, 200

#=====================
# Renaming
#=====================
@api.route('/volumes/<int:id>/rename', methods=['GET','POST'])
@auth
def api_rename(id: int):
	try:
		library.get_volume(id)
	except VolumeNotFound as e:
		return e.api_response

	if request.method == 'GET':
		result = preview_mass_rename(id)
		return {'error': None, 'result': result}, 200
		
	elif request.method == 'POST':
		mass_rename(id)
		return {'error': None, 'result': None}, 200

@api.route('/issues/<int:id>/rename', methods=['GET','POST'])
@auth
def api_rename_issue(id: int):
	try:
		volume_id = library.get_issue(id).get_info()['volume_id']
	except IssueNotFound as e:
		return e.api_response

	if request.method == 'GET':
		result = preview_mass_rename(volume_id, id)
		return {'error': None, 'result': result}, 200
		
	elif request.method == 'POST':
		mass_rename(volume_id, id)
		return {'error': None, 'result': None}, 200

#=====================
# Manual search + Download
#=====================
@api.route('/volumes/<int:id>/manualsearch', methods=['GET'])
@auth
def api_volume_manual_search(id: int):
	try:
		volume_info = library.get_volume(id).get_info(complete=False)
		result = manual_search(volume_info['title'], volume_info['volume_number'], volume_info['year'])
		return {'error': None, 'result': result}, 200
	except VolumeNotFound as e:
		return e.api_response

@api.route('/volumes/<int:id>/download', methods=['POST'])
@auth
def api_volume_download(id: int):
	try:
		link = extract_key(request, 'link')
		library.get_volume(id)
		result = download_handler.add(link, id)
	except (VolumeNotFound, KeyNotFound) as e:
		return e.api_response
	else:
		return {'error': None, 'result': result}, 201

@api.route('/issues/<int:id>/manualsearch', methods=['GET'])
@auth
def api_issue_manual_search(id: int):
	try:
		issue_info = library.get_issue(id).get_info()
		volume_info = library.get_volume(issue_info['volume_id']).get_info(complete=False)
		result = manual_search(volume_info['title'], volume_info['volume_number'], volume_info['year'], issue_info['issue_number'])
		return {'error': None, 'result': result}, 200
	except IssueNotFound as e:
		return e.api_response

@api.route('/issues/<int:id>/download', methods=['POST'])
@auth
def api_issue_download(id: int):
	try:
		link = extract_key(request, 'link')
		issue_info = library.get_issue(id).get_info()
		result = download_handler.add(link, issue_info['volume_id'], id)
	except (VolumeNotFound, KeyNotFound) as e:
		return e.api_response
	else:
		return {'error': None, 'result': result}, 201

@api.route('/activity/queue', methods=['GET'])
@auth
def api_downloads():
	result = download_handler.get_all()
	return {'error': None, 'result': result}, 200

@api.route('/activity/queue/<int:download_id>', methods=['GET','DELETE'])
@auth
def api_delete_download(download_id: int):
	if request.method == 'GET':
		try:
			result = download_handler.get_one(download_id)
		except DownloadNotFound as e:
			return e.api_response
		else:
			return {'error': None, 'result': result}, 200

	elif request.method == 'DELETE':
		try:
			download_handler.remove(download_id)
		except DownloadNotFound as e:
			return e.api_response
		else:
			return {'error': None, 'result': {}}, 200

@api.route('/activity/history', methods=['GET','DELETE'])
@auth
def api_download_history():
	if request.method == 'GET':
		try:
			offset = extract_key(request, 'offset', False)
		except InvalidKeyValue as e:
			return e.api_response
		else:
			result = get_download_history(offset)
			return {'error': None, 'result': result}, 200

	elif request.method == 'DELETE':
		delete_download_history()
		return {'error': None, 'result': {}}, 200

#=====================
# Blocklist
#=====================
@api.route('/blocklist', methods=['GET', 'POST', 'DELETE'])
@auth
def api_blocklist():
	if request.method == 'GET':
		result = get_blocklist()
		return {'error': None, 'result': result}, 200
	
	elif request.method == 'POST':
		try:
			link = extract_key(request, 'link')
			reason_id = extract_key(request, 'reason_id')
			result = add_to_blocklist(link, reason_id)
		except (KeyNotFound, InvalidKeyValue) as e:
			return e.api_response
		else:
			return {'error': None, 'result': result}, 201
	
	elif request.method == 'DELETE':
		delete_blocklist()
		return {'error': None, 'result': {}}, 200

@api.route('/blocklist/<int:id>', methods=['GET', 'DELETE'])
@auth
def api_blocklist_entry(id: int):
	if request.method == 'GET':
		try:
			result = get_blocklist_entry(id)
		except BlocklistEntryNotFound as e:
			return e.api_response
		else:
			return {'error': None, 'result': result}, 200

	elif request.method == 'DELETE':
		try:
			delete_blocklist_entry(id)
		except BlocklistEntryNotFound as e:
			return e.api_response
		else:
			return {'error': None, 'result': {}}, 200
