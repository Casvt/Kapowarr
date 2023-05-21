#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import logging
from os import makedirs, urandom
from sqlite3 import OperationalError
from sys import version_info

from flask import Flask, render_template, request
from waitress.server import create_server
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from backend.db import close_db, get_db, set_db_location, setup_db
from backend.files import folder_path
from backend.logging import set_log_level, setup_logging
from backend.settings import default_settings, private_settings
from frontend.api import (about_data, api, download_handler, settings,
                          task_handler, ui_vars)
from frontend.ui import ui

DB_FILENAME = 'db', 'Kapowarr.db'

def _create_app() -> Flask:
	"""Creates an flask app instance that can be used to start a web server

	Returns:
		Flask: The app instance
	"""
	app = Flask(
		__name__,
		template_folder=folder_path('frontend','templates'),
		static_folder=folder_path('frontend','static'),
		static_url_path='/static'
	)
	app.config['SECRET_KEY'] = urandom(32)
	app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
	app.config['JSON_SORT_KEYS'] = False

	# Add error handlers
	@app.errorhandler(404)
	def not_found(e):
		if request.path.startswith('/api'):
			return {'error': 'NotFound', 'result': {}}, 404
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

	# Add endpoints
	app.register_blueprint(ui)
	app.register_blueprint(api, url_prefix="/api")

	# Setup db handling
	app.teardown_appcontext(close_db)

	return app

def Kapowarr() -> None:
	"""The main function of Kapowarr
	"""
	setup_logging()
	logging.info('Starting up Kapowarr')

	# Check python version
	if (version_info.major < 3) or (version_info.major == 3 and version_info.minor < 7):
		logging.critical('The minimum python version required is python3.7 (currently ' + version_info.major + '.' + version_info.minor + '.' + version_info.micro + ')')
		exit(1)

	# Register web server
	app = _create_app()

	# Setup database, folders and logging
	with app.app_context():
		set_db_location(folder_path(*DB_FILENAME))
		about_data.update({'database_location': folder_path(*DB_FILENAME)})
		
		# Set log level
		cursor = get_db()
		try:
			log_level = cursor.execute(
				"SELECT value FROM config WHERE key = 'log_level' LIMIT 1;"
			).fetchone()[0]
			set_log_level(log_level)
		except OperationalError:
			set_log_level(default_settings['log_level'])

		# Setup db
		setup_db()
		
		# Set url base if needed
#		url_base = cursor.execute("SELECT value FROM config WHERE key = 'url_base' LIMIT 1;").fetchone()[0]
		url_base = settings.get_settings()['url_base']
		app.config['APPLICATION_ROOT'] = url_base
		app.wsgi_app = DispatcherMiddleware(Flask(__name__), {url_base: app.wsgi_app})
		ui_vars.update({'url_base': url_base})

		# Create download folder if needed
		logging.debug('Creating download folder if needed')
		makedirs(settings.cache['download_folder'], exist_ok=True)

	# Now that database is setup, start handlers
	download_handler.load_download_thread.start()
	task_handler.handle_intervals()

	# Create waitress server and run
	logging.debug('Creating server')
	server = create_server(
		app,
		host=settings.cache['host'],
		port=settings.cache['port'],
		threads=private_settings['hosting_threads']
	)
	logging.info(f'Kapowarr running on http://{settings.cache["host"]}:{settings.cache["port"]}{settings.cache["url_base"]}/')
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
