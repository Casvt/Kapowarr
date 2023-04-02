#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import logging
from os import makedirs, urandom
from os.path import dirname
from sys import version_info

from flask import Flask, render_template, request
from waitress.server import create_server

from backend.db import DBConnection, close_db, setup_db
from backend.files import folder_path
from backend.helpers import set_log_level
from backend.settings import private_settings
from frontend.api import api, download_handler, settings, task_handler
from frontend.ui import ui

DB_FILENAME = 'db', 'Kapowarr.db'

logging.basicConfig(
	level=logging.INFO,
	format='[%(asctime)s][%(threadName)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
)

def _create_app() -> Flask:
	app = Flask(
		__name__,
		template_folder=folder_path('frontend','templates'),
		static_folder=folder_path('frontend','static'),
		static_url_path='/static'
	)
	app.config['SECRET_KEY'] = urandom(32)
	app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
	app.config['JSON_SORT_KEYS'] = False

	#add error handlers
	@app.errorhandler(404)
	def not_found(e):
		if request.path.startswith('/api'):
			return {'error': 'NotFound', 'result': {}}, 404
		else:
			return render_template('page_not_found.html')

	@app.errorhandler(400)
	def bad_request(e):
		return {'error': 'BadRequest', 'result': {}}, 400

	@app.errorhandler(405)
	def method_not_allowed(e):
		return {'error': 'MethodNotAllowed', 'result': {}}, 405

	@app.errorhandler(500)
	def internal_error(e):
		return {'error': 'InternalError', 'result': {}}, 500

	#add endpoints
	app.register_blueprint(ui)
	app.register_blueprint(api, url_prefix="/api")

	#setup db handling
	app.teardown_appcontext(close_db)

	return app

def Kapowarr() -> None:
	"""The main function of Kapowarr

	Returns:
		None
	"""
	logging.info('Starting up Kapowarr')
	# Check python version
	if (version_info.major < 3) or (version_info.major == 3 and version_info.minor < 7):
		logging.error('The minimum python version required is python3.7 (currently ' + version_info.major + '.' + version_info.minor + '.' + version_info.micro + ')')
		return

	# Register web server
	app = _create_app()

	# Setup logging and database
	with app.app_context():
		
		db_location = folder_path(*DB_FILENAME)
		makedirs(dirname(db_location), exist_ok=True)
		DBConnection.file = db_location
		setup_db()

		makedirs(settings.get_settings()['download_folder'], exist_ok=True)

		# Setup logging
		set_log_level(settings.get_settings()['log_level'])

	# Now that database is setup, start handlers
	download_handler.thread.start()
	task_handler.thread.start()

	# Create waitress server and run
	server = create_server(
		app,
		host=settings.cache['host'],
		port=settings.cache['port'],
		threads=private_settings['hosting_threads']
	)
	logging.info(f'Kapowarr running on http://{settings.cache["host"]}:{settings.cache["port"]}/')
	# Below is run endlessly until CTRL+C
	server.run()

	# Shutdown application
	logging.info('Stopping Kapowarr')
	download_handler.stop_handle()
	task_handler.stop_handle()

	logging.info('Thank you for using Kapowarr')
	return

if __name__ == "__main__":
	Kapowarr()
