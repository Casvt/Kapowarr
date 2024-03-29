#-*- coding: utf-8 -*-

from flask import Blueprint, redirect, render_template

ui = Blueprint('ui', __name__)

methods = ['GET']

ui_vars = {}

@ui.route('/login', methods=methods)
def ui_login():
	return render_template('login.html', url_base=ui_vars['url_base'])

@ui.route('/', methods=methods)
def ui_volumes():
	return render_template('volumes.html', url_base=ui_vars['url_base'])

@ui.route('/add', methods=methods)
def ui_add_volume():
	return render_template('add_volume.html', url_base=ui_vars['url_base'])

@ui.route('/library-import', methods=methods)
def ui_library_import():
	return render_template('library_import.html', url_base=ui_vars['url_base'])

@ui.route('/volumes/<id>', methods=methods)
def ui_view_volume(id):
	return render_template('view_volume.html', url_base=ui_vars['url_base'])

@ui.route('/activity/queue', methods=methods)
def ui_queue():
	return render_template('queue.html', url_base=ui_vars['url_base'])

@ui.route('/activity/history', methods=methods)
def ui_history():
	return render_template('history.html', url_base=ui_vars['url_base'])

@ui.route('/activity/blocklist', methods=methods)
def ui_blocklist():
	return render_template('blocklist.html', url_base=ui_vars['url_base'])

@ui.route('/system/status', methods=methods)
def ui_status():
	return render_template('status.html', url_base=ui_vars['url_base'])

@ui.route('/system/tasks', methods=methods)
def ui_tasks():
	return render_template('tasks.html', url_base=ui_vars['url_base'])

@ui.route('/settings', methods=methods)
def ui_settings():
	return redirect(f'{ui_vars["url_base"]}/settings/mediamanagement')

@ui.route('/settings/mediamanagement', methods=methods)
def ui_mediamanagement():
	return render_template('settings_mediamanagement.html', url_base=ui_vars['url_base'])

@ui.route('/settings/download', methods=methods)
def ui_download():
	return render_template('settings_download.html', url_base=ui_vars['url_base'])

@ui.route('/settings/downloadclients', methods=methods)
def ui_download_clients():
	return render_template('settings_download_clients.html', url_base=ui_vars['url_base'])

@ui.route('/settings/general', methods=methods)
def ui_general():
	return render_template('settings_general.html', url_base=ui_vars['url_base'])
