#-*- coding: utf-8 -*-

from flask import Blueprint, redirect, render_template

ui = Blueprint('ui', __name__)

methods = ['GET']

@ui.route('/login', methods=methods)
def ui_login():
	return render_template('login.html')

@ui.route('/', methods=methods)
def ui_volumes():
	return render_template('volumes.html')

@ui.route('/add', methods=methods)
def ui_add_volume():
	return render_template('add_volume.html')

@ui.route('/volumes/<id>', methods=methods)
def ui_view_volume(id):
	return render_template('view_volume.html')

@ui.route('/activity/queue', methods=methods)
def ui_queue():
	return render_template('queue.html')

@ui.route('/activity/history', methods=methods)
def ui_history():
	return render_template('history.html')
	
@ui.route('/activity/blocklist', methods=methods)
def ui_blocklist():
	return render_template('blocklist.html')

@ui.route('/system/status', methods=methods)
def ui_status():
	return render_template('status.html')

@ui.route('/system/tasks', methods=methods)
def ui_tasks():
	return render_template('tasks.html')

@ui.route('/settings', methods=methods)
def ui_settings():
	return redirect('/settings/mediamanagement')
	
@ui.route('/settings/mediamanagement', methods=methods)
def ui_mediamanagement():
	return render_template('settings_mediamanagement.html')

@ui.route('/settings/download', methods=methods)
def ui_download():
	return render_template('settings_download.html')

@ui.route('/settings/general', methods=methods)
def ui_general():
	return render_template('settings_general.html')
